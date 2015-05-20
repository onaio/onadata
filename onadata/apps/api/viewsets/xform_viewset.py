import os
import json
import random

from datetime import datetime

from celery.result import AsyncResult
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.contrib.auth.models import User
from django.conf import settings
from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.utils import six
from django.utils import timezone

from pyxform.xls2json import parse_file_to_json
from pyxform.builder import create_survey_element_from_dict
from rest_framework import exceptions
from rest_framework import status
from rest_framework.decorators import action, detail_route, list_route
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ParseError
from rest_framework.filters import DjangoFilterBackend

from onadata.apps.main.views import get_enketo_preview_url
from onadata.apps.api import tasks
from onadata.apps.viewer import tasks as viewer_task
from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.labels_mixin import LabelsMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.renderers import renderers
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.serializers.clone_xform_serializer import \
    CloneXFormSerializer
from onadata.libs.serializers.share_xform_serializer import (
    ShareXFormSerializer)
from onadata.apps.api import tools as utils
from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.viewer_tools import (
    enketo_url,
    EnketoError,
    generate_enketo_form_defaults)
from onadata.apps.viewer.models.export import Export
from onadata.libs.exceptions import NoRecordsFoundError, J2XException
from onadata.libs.utils.export_tools import generate_export
from onadata.libs.utils.export_tools import generate_kml_export
from onadata.libs.utils.export_tools import generate_external_export
from onadata.libs.utils.export_tools import generate_osm_export
from onadata.libs.utils.export_tools import should_create_new_export
from onadata.libs.utils.common_tags import OSM
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils import log
from onadata.libs.utils.export_tools import newest_export_for
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.logger_tools import publish_form
from onadata.libs.utils.string import str2bool

from onadata.libs.utils.csv_import import get_async_csv_submission_status
from onadata.libs.utils.csv_import import submit_csv
from onadata.libs.utils.csv_import import submit_csv_async
from onadata.libs.utils.viewer_tools import _get_form_url
from onadata.libs.utils.export_tools import str_to_bool


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

# Supported external exports
external_export_types = ['xls']


def upload_to_survey_draft(filename, username):
    return os.path.join(
        username,
        'survey-drafts',
        os.path.split(filename)[1]
    )


def get_survey_dict(csv_name):
    survey_file = default_storage.open(csv_name, 'r')
    survey_dict = parse_file_to_json(
        survey_file.name, default_name='data', file_object=survey_file)

    return survey_dict


def _get_export_type(export_type):
    if export_type in EXPORT_EXT.keys():
        export_type = EXPORT_EXT[export_type]
    else:
        raise exceptions.ParseError(
            _(u"'%(export_type)s' format not known or not implemented!" %
              {'export_type': export_type})
        )

    return export_type


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


def _export_async_export_response(request, xform, export):
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

    if should_regenerate_export(xform, export_type, request)\
            or export_type == Export.EXTERNAL_EXPORT:

        resp = {
            u'job_uuid': _create_export_async(xform, export_type,
                                              query, False,
                                              options=options)
        }
    else:
        export = newest_export_for(xform, export_type)

        if not export.filename:
            # tends to happen when using newest_export_for.
            resp = {
                u'job_uuid': _create_export_async(xform, export_type,
                                                  query, False,
                                                  options=options)
            }
        else:
            resp = _export_async_export_response(request, xform, export)

    return resp


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


def _generate_new_export(request, xform, query, export_type):
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

            if "remove_group_name" in request.QUERY_PARAMS:
                remove_group_name = \
                    str_to_bool(request.QUERY_PARAMS["remove_group_name"])

            export = generate_export(
                export_type, extension, xform.user.username,
                xform.id_string, None, query,
                remove_group_name=remove_group_name
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


def _get_user(username):
    users = User.objects.filter(username__iexact=username)

    return users.count() and users[0] or None


def _get_owner(request):
    owner = request.DATA.get('owner') or request.user

    if isinstance(owner, six.string_types):
        owner_obj = _get_user(owner)

        if owner_obj is None:
            raise ValidationError(
                u"User with username %s does not exist." % owner)
        else:
            owner = owner_obj

    return owner


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


def should_regenerate_export(xform, export_type, request):
    return should_create_new_export(xform, export_type) or\
        'start' in request.GET or 'end' in request.GET or\
        'query' in request.GET or 'data_id' in request.GET


def value_for_type(form, field, value):
    if form._meta.get_field(field).get_internal_type() == 'BooleanField':
        return str2bool(value)

    return value


def external_export_response(export):
    if isinstance(export, Export) \
            and export.internal_status == Export.SUCCESSFUL:
        return HttpResponseRedirect(export.export_url)
    else:
        http_status = status.HTTP_400_BAD_REQUEST

    return Response(json.dumps(export), http_status,
                    content_type="application/json")


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


def custom_response_handler(request, xform, query, export_type,
                            token=None, meta=None):
    export_type = _get_export_type(export_type)

    if export_type in external_export_types and \
            (token is not None) or (meta is not None):
        export_type = Export.EXTERNAL_EXPORT

    # check if we need to re-generate,
    # we always re-generate if a filter is specified
    if should_regenerate_export(xform, export_type, request):
        export = _generate_new_export(request, xform, query, export_type)
    else:
        export = newest_export_for(xform, export_type)
        if not export.filename:
            # tends to happen when using newset_export_for.
            export = _generate_new_export(request, xform, query, export_type)

    log_export(request, xform, export_type)

    if export_type == Export.EXTERNAL_EXPORT:
        return external_export_response(export)

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    path, ext = os.path.splitext(export.filename)
    ext = ext[1:]
    id_string = None if request.GET.get('raw') else xform.id_string
    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext], id_string, extension=ext,
        file_path=export.filepath)

    return response


def _try_update_xlsform(request, xform, owner):
    survey = \
        utils.publish_xlsform(request, owner, xform.id_string, xform.project)

    if isinstance(survey, XForm):
        serializer = XFormSerializer(
            xform, context={'request': request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(survey, status=status.HTTP_400_BAD_REQUEST)


def result_has_error(result):
    return isinstance(result, dict) and result.get('type')


def get_survey_xml(csv_name):
    survey_dict = get_survey_dict(csv_name)
    survey = create_survey_element_from_dict(survey_dict)
    return survey.to_xml()


class XFormViewSet(AnonymousUserPublicFormsMixin,
                   LabelsMixin,
                   LastModifiedMixin,
                   ModelViewSet):
    """
    Publish XLSForms, List, Retrieve Published Forms.
    """

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.SurveyRenderer,
        renderers.OSMExportRenderer
    ]
    queryset = XForm.objects.select_related()
    serializer_class = XFormSerializer
    lookup_field = 'pk'
    extra_lookup_fields = None
    permission_classes = [XFormPermissions, ]
    updatable_fields = set(('description', 'downloadable', 'require_auth',
                            'shared', 'shared_data', 'title'))
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.TagFilter,
                       filters.XFormOwnerFilter,
                       DjangoFilterBackend)
    filter_fields = ('instances_with_osm',)

    public_forms_endpoint = 'public'

    def create(self, request, *args, **kwargs):
        try:
            owner = _get_owner(request)
        except ValidationError as e:
            return Response({'message': e.messages[0]},
                            status=status.HTTP_400_BAD_REQUEST)

        survey = utils.publish_xlsform(request, owner)
        if isinstance(survey, XForm):
            xform = XForm.objects.get(pk=survey.pk)
            serializer = XFormSerializer(
                xform, context={'request': request})
            headers = self.get_success_headers(serializer.data)

            return Response(serializer.data, status=status.HTTP_201_CREATED,
                            headers=headers)

        return Response(survey, status=status.HTTP_400_BAD_REQUEST)

    @list_route(methods=['POST', 'GET'])
    def create_async(self, request, *args, **kwargs):
        """ Temporary Endpoint for Async form creation """
        resp = headers = {}
        resp_code = status.HTTP_400_BAD_REQUEST

        if request.method == 'GET':
            survey = tasks.get_async_status(
                request.QUERY_PARAMS.get('job_uuid'))

            if 'pk' in survey:
                xform = XForm.objects.get(pk=survey.get('pk'))
                serializer = XFormSerializer(
                    xform, context={'request': request})
                headers = self.get_success_headers(serializer.data)
                resp = serializer.data
                resp_code = status.HTTP_201_CREATED
            else:
                resp_code = status.HTTP_202_ACCEPTED
                resp.update(survey)
        else:
            try:
                owner = _get_owner(request)
            except ValidationError as e:
                return Response({'message': e.messages[0]},
                                status=status.HTTP_400_BAD_REQUEST)

            fname = request.FILES.get('xls_file').name
            resp.update(
                {u'job_uuid':
                 tasks.publish_xlsform_async.delay(
                     request.user, request.POST, owner,
                     ({'name': fname,
                       'data': request.FILES.get('xls_file').read()}
                      if isinstance(request.FILES.get('xls_file'),
                                    InMemoryUploadedFile) else
                      {'name': fname,
                       'path': request.FILES.get(
                           'xls_file').temporary_file_path()})).task_id})
            resp_code = status.HTTP_202_ACCEPTED

        return Response(data=resp, status=resp_code, headers=headers)

    @action(methods=['GET'])
    def form(self, request, format='json', **kwargs):
        form = self.get_object()
        if format not in ['json', 'xml', 'xls']:
            return HttpResponseBadRequest('400 BAD REQUEST',
                                          content_type='application/json',
                                          status=400)
        filename = form.id_string + "." + format
        response = response_for_format(form, format=format)
        response['Content-Disposition'] = 'attachment; filename=' + filename

        return response

    @action(methods=['GET'])
    def enketo(self, request, **kwargs):
        self.object = self.get_object()
        form_url = _get_form_url(request, self.object.user.username)

        data = {'message': _(u"Enketo not properly configured.")}
        http_status = status.HTTP_400_BAD_REQUEST

        try:
            # pass default arguments to enketo_url to prepopulate form fields
            request_vars = request.GET
            defaults = generate_enketo_form_defaults(
                self.object, **request_vars)
            url = enketo_url(form_url, self.object.id_string, **defaults)
            preview_url = get_enketo_preview_url(request,
                                                 request.user.username,
                                                 self.object.id_string)
        except EnketoError:
            pass
        else:
            if url and preview_url:
                http_status = status.HTTP_200_OK
                data = {"enketo_url": url, "enketo_preview_url": preview_url}

        return Response(data, http_status)

    @list_route(methods=['POST', 'GET'])
    def survey_preview(self, request, **kwargs):
        username = request.user.username
        if request.method.upper() == 'POST':
            if not username:
                raise ParseError("User has to be authenticated")

            csv_data = request.DATA.get('body')
            if csv_data:
                rand_name = "survey_draft_%s.csv" % ''.join(
                    random.sample("abcdefghijklmnopqrstuvwxyz0123456789", 6))
                csv_file = ContentFile(csv_data)
                csv_name = default_storage.save(
                    upload_to_survey_draft(rand_name, username),
                    csv_file)

                result = publish_form(lambda: get_survey_xml(csv_name))

                if result_has_error(result):
                    raise ParseError(result.get('text'))

                return Response(
                    {'unique_string': rand_name, 'username': username},
                    status=200)
            else:
                raise ParseError('Missing body')

        if request.method.upper() == 'GET':
            filename = request.QUERY_PARAMS.get('filename')
            username = request.QUERY_PARAMS.get('username')

            if not username:
                raise ParseError('Username not provided')
            if not filename:
                raise ParseError("Filename MUST be provided")

            csv_name = upload_to_survey_draft(filename, username)

            result = publish_form(lambda: get_survey_xml(csv_name))

            if result_has_error(result):
                raise ParseError(result.get('text'))

            return Response(result, status=200)

    def retrieve(self, request, *args, **kwargs):
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)

        if lookup == self.public_forms_endpoint:
            self.object_list = self._get_public_forms_queryset()

            page = self.paginate_queryset(self.object_list)
            if page is not None:
                serializer = self.get_pagination_serializer(page)
            else:
                serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        xform = self.get_object()
        export_type = kwargs.get('format')
        query = request.GET.get("query", request.QUERY_PARAMS.get("query", {}))
        token = request.GET.get('token')
        meta = request.GET.get('meta')

        if export_type is None or export_type in ['json']:
            # perform default viewset retrieve, no data export
            return super(XFormViewSet, self).retrieve(request, *args, **kwargs)

        return custom_response_handler(request,
                                       xform,
                                       query,
                                       export_type,
                                       token,
                                       meta)

    @action(methods=['POST'])
    def share(self, request, *args, **kwargs):
        self.object = self.get_object()

        data = {}
        for key, val in request.DATA.iteritems():
            data[key] = val
        data.update({'xform': self.object.pk})

        serializer = ShareXFormSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['POST'])
    def clone(self, request, *args, **kwargs):
        self.object = self.get_object()
        data = {'xform': self.object.pk,
                'username': request.DATA.get('username')}
        serializer = CloneXFormSerializer(data=data)
        if serializer.is_valid():
            clone_to_user = User.objects.get(username=data['username'])
            if not request.user.has_perm('can_add_xform',
                                         clone_to_user.profile):
                raise exceptions.PermissionDenied(
                    detail=_(u"User %(user)s has no permission to add "
                             "xforms to account %(account)s" %
                             {'user': request.user.username,
                              'account': data['username']}))
            xform = serializer.save()
            serializer = XFormSerializer(
                xform.cloned_form, context={'request': request})

            return Response(data=serializer.data,
                            status=status.HTTP_201_CREATED)

        return Response(data=serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['POST', 'GET'])
    def csv_import(self, request, *args, **kwargs):
        """ Endpoint for CSV data imports
        Calls :py:func:`onadata.libs.utils.csv_import.submit_csv` for POST
        requests passing the `request.FILES.get('csv_file')` upload
        for import and
        :py:func:onadata.libs.utils.csv_import.get_async_csv_submission_status
        for GET requests passing `job_uuid` query param for job progress
        polling
        """
        self.object = self.get_object()
        resp = {}
        if request.method == 'GET':
            resp.update(get_async_csv_submission_status(
                request.QUERY_PARAMS.get('job_uuid')))
            self.last_modified_date = timezone.now()
        else:
            csv_file = request.FILES.get('csv_file', None)
            if csv_file is None:
                resp.update({u'error': u'csv_file field empty'})
            else:
                num_rows = sum(1 for row in csv_file) - 1
                if num_rows < settings.CSV_ROW_IMPORT_ASYNC_THRESHOLD:
                    resp.update(submit_csv(request.user.username,
                                           self.object, csv_file))
                else:
                    task = submit_csv_async.delay(request.user.username,
                                                  self.object,
                                                  csv_file)
                    if task is None:
                        raise ParseError('Task not found')
                    else:
                        resp.update({u'task_id': task.task_id})

        return Response(
            data=resp,
            status=status.HTTP_200_OK if resp.get('error') is None else
            status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        self.object = self.get_object()
        owner = self.object.user

        # updating the file
        if request.FILES:
            return _try_update_xlsform(request, self.object, owner)

        return super(XFormViewSet, self).partial_update(request, *args,
                                                        **kwargs)

    @action(methods=['DELETE', 'GET'])
    def delete_async(self, request, *args, **kwargs):
        if request.method == 'DELETE':
            time_async_triggered = datetime.now()
            self.object = self.get_object()
            self.object.deleted_at = time_async_triggered
            self.object.save()
            xform = self.object
            resp = {
                u'job_uuid': tasks.delete_xform_async.delay(xform).task_id,
                u'time_async_triggered': time_async_triggered}
            resp_code = status.HTTP_202_ACCEPTED

        elif request.method == 'GET':
            job_uuid = request.QUERY_PARAMS.get('job_uuid')
            resp = tasks.get_async_status(job_uuid)
            resp_code = status.HTTP_202_ACCEPTED
        return Response(data=resp, status=resp_code)

    @action(methods=['GET'])
    def export_async(self, request, *args, **kwargs):
        job_uuid = request.QUERY_PARAMS.get('job_uuid')
        export_type = request.QUERY_PARAMS.get('format')
        query = request.QUERY_PARAMS.get("query")
        xform = self.get_object()

        token = request.QUERY_PARAMS.get('token')
        meta = request.QUERY_PARAMS.get('meta')
        data_id = request.QUERY_PARAMS.get('data_id')
        remove_group_name = request.QUERY_PARAMS.get('remove_group_name')

        options = {
            'meta': meta,
            'token': token,
            'data_id': data_id,
            'remove_group_name': remove_group_name
        }

        if job_uuid:
            job = AsyncResult(job_uuid)
            if job.state == 'SUCCESS':
                export_id = job.result
                export = Export.objects.get(id=export_id)

                resp = _export_async_export_response(request, xform, export)
            else:
                resp = {
                    'job_status': job.state
                }

        else:
            resp = process_async_export(request, xform, export_type, query,
                                        token, meta, options)

        return Response(data=resp,
                        status=status.HTTP_202_ACCEPTED,
                        content_type="application/json")
