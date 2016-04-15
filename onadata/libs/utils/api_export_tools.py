import os
import json
from datetime import datetime
from requests import ConnectionError

from django.http import Http404, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils import six
from django.shortcuts import get_object_or_404

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.reverse import reverse

from celery.result import AsyncResult

from oauth2client.contrib.django_orm import Storage
from oauth2client import client as google_client

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import should_create_new_export
from onadata.libs.utils.common_tags import OSM
from onadata.libs.utils import log
from onadata.apps.main.models import TokenStorageModel
from onadata.apps.viewer import tasks as viewer_task
from onadata.libs.exceptions import NoRecordsFoundError, J2XException
from onadata.libs.utils.export_tools import newest_export_for
from onadata.libs.utils.export_tools import generate_attachments_zip_export
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.export_tools import generate_kml_export
from onadata.libs.utils.export_tools import generate_external_export
from onadata.libs.utils.export_tools import generate_osm_export
from onadata.libs.utils.export_tools import parse_request_export_options
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.exceptions import ServiceUnavailable
from onadata.libs.utils.common_tags import SUBMISSION_TIME,\
    GROUPNAME_REMOVED_FLAG, DATAVIEW_EXPORT
from onadata.libs.utils.google import google_flow

# Supported external exports
external_export_types = ['xls']

EXPORT_EXT = {
    'xls': Export.XLS_EXPORT,
    'xlsx': Export.XLS_EXPORT,
    'csv': Export.CSV_EXPORT,
    'csvzip': Export.CSV_ZIP_EXPORT,
    'savzip': Export.SAV_ZIP_EXPORT,
    'uuid': Export.EXTERNAL_EXPORT,
    'kml': Export.KML_EXPORT,
    'zip': Export.ZIP_EXPORT,
    OSM: Export.OSM_EXPORT,
    'gsheets': Export.GOOGLE_SHEETS_EXPORT
}

EXPORT_SUCCESS = "Success"
EXPORT_PENDING = "Pending"
EXPORT_FAILED = "Failed"


def _get_export_type(export_type):
    if export_type in EXPORT_EXT.keys():
        export_type = EXPORT_EXT[export_type]
    else:
        raise exceptions.ParseError(
            _(u"'%(export_type)s' format not known or not implemented!" %
              {'export_type': export_type})
        )

    return export_type


def custom_response_handler(request, xform, query, export_type,
                            token=None, meta=None, dataview_pk=False):
    export_type = _get_export_type(export_type)
    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
        export_type = Export.EXTERNAL_EXPORT

    options = parse_request_export_options(request)

    options["dataview_pk"] = dataview_pk
    options['query'] = query

    remove_group_name = options.get("remove_group_name")

    export_id = request.QUERY_PARAMS.get("export_id")

    if export_id:
        export = get_object_or_404(Export, id=export_id, xform=xform)
    else:
        if export_type == Export.GOOGLE_SHEETS_EXPORT:

                payload = {
                    "details": _("Sheets export only supported in async mode")
                }
                return Response(data=json.dumps(payload),
                                status=status.HTTP_403_FORBIDDEN,
                                content_type="application/json")

        # check if we need to re-generate,
        # we always re-generate if a filter is specified
        def new_export():
            return _generate_new_export(request, xform, query, export_type,
                                        dataview_pk=dataview_pk)

        if should_create_new_export(xform, export_type, options,
                                    request=request):
            export = new_export()
        else:
            export = newest_export_for(xform, export_type, options)

            if not export.filename:
                export = new_export()

        log_export(request, xform, export_type)

        if export_type == Export.EXTERNAL_EXPORT:
            return external_export_response(export)

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    path, ext = os.path.splitext(export.filename)
    ext = ext[1:]

    id_string = _generate_filename(request, xform, remove_group_name,
                                   dataview_pk=dataview_pk)
    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext], id_string, extension=ext,
        file_path=export.filepath)

    return response


def _generate_new_export(request, xform, query, export_type,
                         dataview_pk=False):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    options = {"extension": extension,
               "username": xform.user.username,
               "id_string": xform.id_string,
               "query": query}

    options["dataview_pk"] = dataview_pk
    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        options['google_credentials'] = _get_google_credential(request)

    try:
        if export_type == Export.EXTERNAL_EXPORT:
            options['token'] = request.GET.get('token')
            options['data_id'] = request.GET.get('data_id')
            options['meta'] = request.GET.get('meta')

            export = generate_external_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options, xform=xform)
        elif export_type == Export.OSM_EXPORT:
            export = generate_osm_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options, xform=xform)
        elif export_type == Export.ZIP_EXPORT:
            export = generate_attachments_zip_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options, xform=xform)
        elif export_type == Export.KML_EXPORT:
            export = generate_kml_export(
                export_type,
                xform.user.username,
                xform.id_string,
                None,
                options, xform=xform)
        else:
            options.update(parse_request_export_options(request))

            export = generate_export(
                export_type,
                xform,
                None,
                options)

        audit = {
            "xform": xform.id_string,
            "export_type": export_type
        }
        log.audit_log(
            log.Actions.EXPORT_CREATED, request.user, xform.user,
            _("Created %(export_type)s export on '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
                'export_type': export_type.upper()
            }, audit, request)
    except NoRecordsFoundError:
        raise Http404(_("No records found to export"))
    except J2XException as e:
        # j2x exception
        return {'error': str(e)}
    else:
        return export


def log_export(request, xform, export_type):
    # log download as well
    audit = {
        "xform": xform.id_string,
        "export_type": export_type
    }
    log.audit_log(
        log.Actions.EXPORT_DOWNLOADED, request.user, xform.user,
        _("Downloaded %(export_type)s export on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
            'export_type': export_type.upper()
        }, audit, request)


def external_export_response(export):
    if isinstance(export, Export) \
            and export.internal_status == Export.SUCCESSFUL:
        return HttpResponseRedirect(export.export_url)
    else:
        http_status = status.HTTP_400_BAD_REQUEST

    return Response(json.dumps(export), http_status,
                    content_type="application/json")


def _generate_filename(request, xform, remove_group_name=False,
                       dataview_pk=False):
    if request.GET.get('raw'):
        filename = None
    else:
        # append group name removed flag otherwise use the form id_string
        if remove_group_name:
            filename = "{}-{}".format(xform.id_string, GROUPNAME_REMOVED_FLAG)
        elif dataview_pk:
            filename = "{}-{}".format(xform.id_string, DATAVIEW_EXPORT)
        else:
            filename = xform.id_string

    return filename


def _set_start_end_params(request, query):
    # check for start and end params
    if 'start' in request.GET or 'end' in request.GET:
        query = json.loads(query) \
            if isinstance(query, six.string_types) else query
        query[SUBMISSION_TIME] = {}

        try:
            if request.GET.get('start'):
                query[SUBMISSION_TIME]['$gte'] = _format_date_for_mongo(
                    request.GET['start'], datetime)

            if request.GET.get('end'):
                query[SUBMISSION_TIME]['$lte'] = _format_date_for_mongo(
                    request.GET['end'], datetime)
        except ValueError:
            raise exceptions.ParseError(
                _("Dates must be in the format YY_MM_DD_hh_mm_ss")
            )
        else:
            query = json.dumps(query)

        return query
    else:
        return query


def _get_extension_from_export_type(export_type):
    extension = export_type

    if export_type == Export.XLS_EXPORT:
        extension = 'xlsx'
    elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
        extension = 'zip'

    return extension


def _format_date_for_mongo(x, datetime):
    return datetime.strptime(
        x, '%y_%m_%d_%H_%M_%S').strftime('%Y-%m-%dT%H:%M:%S')


def process_async_export(request, xform, export_type, options=None):
    """
    Check if should generate export or just return the latest export.
    Rules for regenerating an export are:
        1. Filter included on the exports.
        2. New submission done.
        3. Always regenerate external exports.
            (External exports uses templates and the template might have
             changed)
    :param request:
    :param xform:
    :param export_type:
    :param options: additional export params that may include
        query: export filter
        token: template url for xls external reports
        meta: metadataid that contains the external xls report template url
        remove_group_name: Flag to determine if group names should appear
    :return: response dictionary
    """
    # maintain the order of keys while processing the export

    export_type = _get_export_type(export_type)
    token = options.get("token")
    meta = options.get("meta")
    query = options.get("query")

    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
                export_type = Export.EXTERNAL_EXPORT

    dataview_pk = options.get('dataview_pk')
    if export_type == Export.GOOGLE_SHEETS_EXPORT:
        credential = _get_google_credential(request)

        if isinstance(credential, HttpResponseRedirect):
            return credential
        options['google_credentials'] = credential

    if should_create_new_export(xform, export_type, options, request=request)\
            or export_type == Export.EXTERNAL_EXPORT:
        resp = {
            u'job_uuid': _create_export_async(xform, export_type,
                                              query, False,
                                              options=options)
        }
    else:
        export = newest_export_for(xform, export_type, options)

        if not export.filename:
            # tends to happen when using newest_export_for.
            resp = {
                u'job_uuid': _create_export_async(xform, export_type,
                                                  query, False,
                                                  options=options)
            }
        else:
            resp = _export_async_export_response(request, xform, export,
                                                 dataview_pk=dataview_pk)

    return resp


def _create_export_async(xform, export_type, query=None, force_xlsx=False,
                         options=None):
        """
        Creates async exports
        :param xform:
        :param export_type:
        :param query:
        :param force_xlsx:
        :param options:
        :return:
            job_uuid generated
        """
        export, async_result \
            = viewer_task.create_async_export(xform, export_type, query,
                                              force_xlsx, options=options)
        return async_result.task_id


def _export_async_export_response(request, xform, export, dataview_pk=None):
    """
    Checks the export status and generates the reponse
    :param request:
    :param xform:
    :param export:
    :return: response dict
    """
    if export.status == Export.SUCCESSFUL:
        if export.export_type not in [Export.EXTERNAL_EXPORT,
                                      Export.GOOGLE_SHEETS_EXPORT]:
            export_url = reverse(
                'export-detail',
                kwargs={'pk': export.pk},
                request=request)
        else:
            export_url = export.export_url
        resp = {
            u'job_status': EXPORT_SUCCESS,
            u'export_url': export_url
        }
    elif export.status == Export.PENDING:
        resp = {
            'export_status': EXPORT_PENDING
        }
    else:
        resp = {
            'export_status': EXPORT_FAILED
        }

    return resp


def get_async_response(job_uuid, request, xform, count=0):
    try:
        job = AsyncResult(job_uuid)
        if job.state == 'SUCCESS':
            export_id = job.result
            export = Export.objects.get(id=export_id)

            resp = _export_async_export_response(
                request, xform, export)
        else:
            resp = {
                'job_status': job.state
            }
    except ConnectionError, e:
        if count > 0:
            raise ServiceUnavailable(unicode(e))

        return get_async_response(job_uuid, request, xform, count + 1)

    return resp


def response_for_format(data, format=None):
    if format == 'xml':
        formatted_data = data.xml
    elif format == 'xls':
        if not data.xls:
            raise Http404()

        formatted_data = data.xls
    else:
        formatted_data = json.loads(data.json)
    return Response(formatted_data)


def _get_google_credential(request):
    token = None
    if request.user.is_authenticated():
        storage = Storage(TokenStorageModel, 'id', request.user, 'credential')
        credential = storage.get()
    elif request.session.get('access_token'):
        credential = google_client.OAuth2Credentials.from_json(token)
    if credential is None:
        return HttpResponseRedirect(google_flow.step1_get_authorize_url())
    return credential
