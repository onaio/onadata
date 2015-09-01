import os
import json
from datetime import datetime
from requests import ConnectionError

from django.http import Http404, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils import six

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.reverse import reverse

from celery.result import AsyncResult

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import should_create_new_export
from onadata.libs.utils.export_tools import str_to_bool
from onadata.libs.utils.common_tags import OSM
from onadata.libs.utils import log
from onadata.apps.viewer import tasks as viewer_task
from onadata.libs.exceptions import NoRecordsFoundError, J2XException
from onadata.libs.utils.export_tools import newest_export_for
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.export_tools import generate_kml_export
from onadata.libs.utils.export_tools import generate_external_export
from onadata.libs.utils.export_tools import generate_osm_export
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.exceptions import ServiceUnavailable
from onadata.libs.utils.common_tags import SUBMISSION_TIME,\
    GROUPNAME_REMOVED_FLAG, DATAVIEW_EXPORT

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
    OSM: Export.OSM_EXPORT
}


def _get_export_type(export_type):
    if export_type in EXPORT_EXT.keys():
        export_type = EXPORT_EXT[export_type]
    else:
        raise exceptions.ParseError(
            _(u"'%(export_type)s' format not known or not implemented!" %
              {'export_type': export_type})
        )

    return export_type


def should_regenerate_export(xform, export_type, request,
                             remove_group_name=False, dataview=None):
    return should_create_new_export(xform, export_type,
                                    remove_group_name=remove_group_name,
                                    dataview=dataview) or\
        'start' in request.GET or 'end' in request.GET or\
        'query' in request.GET or 'data_id' in request.GET


def custom_response_handler(request, xform, query, export_type,
                            token=None, meta=None, dataview=None):
    export_type = _get_export_type(export_type)
    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
        export_type = Export.EXTERNAL_EXPORT

    split_select_multiples = None
    remove_group_name = str_to_bool(request.GET.get('remove_group_name'))
    group_delimiter = request.GET.get('group_delimiter')
    if request.GET.get("dont_split_select_multiples"):
        split_select_multiples = request.GET.get(
            "dont_split_select_multiples", "no") == "no"

    # check if we need to re-generate,
    # we always re-generate if a filter is specified

    if should_regenerate_export(xform, export_type, request,
                                remove_group_name=remove_group_name,
                                dataview=dataview) \
            or group_delimiter in ['.', '/'] \
            or split_select_multiples in [True, False]:
        export = _generate_new_export(request, xform, query, export_type,
                                      dataview=dataview)
    else:
        export = newest_export_for(xform, export_type, remove_group_name,
                                   dataview=dataview)

        if not export.filename:
            # tends to happen when using newset_export_for.
            export = _generate_new_export(request, xform, query, export_type,
                                          dataview=dataview)

    log_export(request, xform, export_type)

    if export_type == Export.EXTERNAL_EXPORT:
        return external_export_response(export)

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    path, ext = os.path.splitext(export.filename)
    ext = ext[1:]

    id_string = _generate_filename(request, xform, remove_group_name,
                                   dataview=dataview)
    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext], id_string, extension=ext,
        file_path=export.filepath)

    return response


def _generate_new_export(request, xform, query, export_type, dataview=None):
    query = _set_start_end_params(request, query)
    extension = _get_extension_from_export_type(export_type)

    try:
        if export_type == Export.EXTERNAL_EXPORT:
            export = generate_external_export(
                export_type, xform.user.username,
                xform.id_string, None, request.GET.get('token'), query,
                request.GET.get('meta'), request.GET.get('data_id')
            )
        elif export_type == Export.OSM_EXPORT:
            export = generate_osm_export(
                export_type, extension, xform.user.username,
                xform.id_string, export_id=None, filter_query=None)
        elif export_type == Export.KML_EXPORT:
            export = generate_kml_export(
                export_type, extension, xform.user.username,
                xform.id_string, export_id=None, filter_query=None)
        else:
            remove_group_name = False
            group_delimiter = '/'
            split_select_multiples = True

            if "remove_group_name" in request.QUERY_PARAMS:
                remove_group_name = \
                    str_to_bool(request.QUERY_PARAMS["remove_group_name"])
            if 'group_delimiter' in request.QUERY_PARAMS and \
                    request.QUERY_PARAMS.get('group_delimiter') in ['.', '/']:
                group_delimiter = request.QUERY_PARAMS["group_delimiter"]
            if 'dont_split_select_multiples' in request.QUERY_PARAMS:
                split_select_multiples = request.QUERY_PARAMS.get(
                    "dont_split_select_multiples", "no") == "no"

            dataview_pk = dataview.pk if dataview else None
            export = generate_export(
                export_type, extension, xform.user.username,
                xform.id_string, None, query,
                remove_group_name=remove_group_name, dataview_pk=dataview_pk,
                group_delimiter=group_delimiter,
                split_select_multiples=split_select_multiples
            )
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
                       dataview=False):
    if request.GET.get('raw'):
        filename = None
    else:
        # append group name removed flag otherwise use the form id_string
        if remove_group_name:
            filename = "{}-{}".format(xform.id_string, GROUPNAME_REMOVED_FLAG)
        elif dataview:
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


def export_async_export_response(request, xform, export, dataview_pk=None):
    """
    Checks the export status and generates the reponse
    :param request:
    :param xform:
    :param export:
    :return: response dict
    """
    if export.status == Export.SUCCESSFUL:
        if export.export_type != Export.EXTERNAL_EXPORT:
            export_url = reverse(
                'xform-detail',
                kwargs={'pk': xform.pk,
                        'format': export.export_type},
                request=request
            )
            if dataview_pk:
                export_url = reverse(
                    'dataviews-data',
                    kwargs={'pk': dataview_pk,
                            'action': 'data',
                            'format': export.export_type},
                    request=request
                )
            remove_group_key = "remove_group_name"
            if str_to_bool(request.QUERY_PARAMS.get(remove_group_key)):
                # append the param to the url
                export_url = "{}?{}=true".format(export_url, remove_group_key)
        else:
            export_url = export.export_url
        resp = {
            u'job_status': "Success",
            u'export_url': export_url
        }
    elif export.status == Export.PENDING:
        resp = {
            'export_status': 'Pending'
        }
    else:
        resp = {
            'export_status': "Failed"
        }

    return resp


def process_async_export(request, xform, export_type, query=None, token=None,
                         meta=None, options=None):
    """
    Check if should generate export or just return the latest export.
    Rules for regenerating an export are:
        1. Filter included on the exports.
        2. New submission done.
        3. Always regenerate external exports.
            (External exports uses templates and the template might have
             changed)
        4. When group delimiter is not None and is either '.' or '/'
    :param request:
    :param xform:
    :param export_type:
    :param query: export filter
    :param token: template url for xls external reports
    :param meta: metadataid that contains the external xls report template url
    :param options: additional export params
    :return: response dictionary
    """

    export_type = _get_export_type(export_type)

    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
                export_type = Export.EXTERNAL_EXPORT

    remove_group_name = str_to_bool(options.get('remove_group_name'))
    group_delimiter = options.get('group_delimiter')
    dataview_pk = options.get('dataview_pk')
    if should_regenerate_export(xform, export_type, request, remove_group_name,
                                dataview_pk)\
            or export_type == Export.EXTERNAL_EXPORT \
            or group_delimiter in ['.', '/']:

        resp = {
            u'job_uuid': _create_export_async(xform, export_type,
                                              query, False,
                                              options=options)
        }
    else:
        remove_group_name = options.get('remove_group_name')
        export = newest_export_for(xform, export_type, remove_group_name,
                                   dataview_pk)

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
        if export.export_type != Export.EXTERNAL_EXPORT:
            export_url = reverse(
                'xform-detail',
                kwargs={'pk': xform.pk,
                        'format': export.export_type},
                request=request
            )
            if dataview_pk:
                export_url = reverse(
                    'dataviews-data',
                    kwargs={'pk': dataview_pk,
                            'action': 'data',
                            'format': export.export_type},
                    request=request
                )
            remove_group_key = "remove_group_name"
            if str_to_bool(request.QUERY_PARAMS.get(remove_group_key)):
                # append the param to the url
                export_url = "{}?{}=true".format(export_url, remove_group_key)
        else:
            export_url = export.export_url
        resp = {
            u'job_status': "Success",
            u'export_url': export_url
        }
    elif export.status == Export.PENDING:
        resp = {
            'export_status': 'Pending'
        }
    else:
        resp = {
            'export_status': "Failed"
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
