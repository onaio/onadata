from past.builtins import basestring

from django.db.models.signals import post_delete, post_save
from django.http import Http404, HttpResponseBadRequest

from celery.result import AsyncResult
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import DataViewViewsetPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.viewer.models.export import Export
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers import renderers
from onadata.libs.serializers.data_serializer import JsonDataSerializer
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils import common_tags
from onadata.libs.utils.api_export_tools import (custom_response_handler,
                                                 export_async_export_response,
                                                 include_hxl_row,
                                                 process_async_export,
                                                 response_for_format)
from onadata.libs.utils.cache_tools import (PROJECT_LINKED_DATAVIEWS,
                                            safe_delete)
from onadata.libs.utils.chart_tools import (get_chart_data_for_field,
                                            get_field_from_field_name)
from onadata.libs.utils.export_tools import str_to_bool
from onadata.libs.utils.model_tools import get_columns_with_hxl

BaseViewset = get_baseviewset_class()


def get_form_field_chart_url(url, field):
    return u'%s?field_name=%s' % (url, field)


class DataViewViewSet(AuthenticateHeaderMixin,
                      CacheControlMixin, ETagsMixin, BaseViewset,
                      ModelViewSet):
    """
    A simple ViewSet for viewing and editing DataViews.
    """

    queryset = DataView.objects.select_related()
    serializer_class = DataViewSerializer
    permission_classes = [DataViewViewsetPermissions]
    lookup_field = 'pk'
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.ZipRenderer,
    ]

    def get_serializer_class(self):
        if self.action == 'data':
            serializer_class = JsonDataSerializer
        else:
            serializer_class = self.serializer_class

        return serializer_class

    @action(methods=['GET'], detail=True)
    def data(self, request, format='json', **kwargs):
        """Retrieve the data from the xform using this dataview"""
        start = request.GET.get("start")
        limit = request.GET.get("limit")
        count = request.GET.get("count")
        sort = request.GET.get("sort")
        query = request.GET.get("query")
        export_type = self.kwargs.get('format', request.GET.get("format"))
        self.object = self.get_object()

        if export_type is None or export_type in ['json', 'debug']:
            data = DataView.query_data(self.object, start, limit,
                                       str_to_bool(count), sort=sort,
                                       filter_query=query)
            if 'error' in data:
                raise ParseError(data.get('error'))

            serializer = self.get_serializer(data, many=True)

            return Response(serializer.data)

        else:
            return custom_response_handler(request, self.object.xform, query,
                                           export_type,
                                           dataview=self.object)

    @action(methods=['GET'], detail=True)
    def export_async(self, request, *args, **kwargs):
        params = request.query_params
        job_uuid = params.get('job_uuid')
        export_type = params.get('format')
        include_hxl = params.get('include_hxl', False)
        include_labels = params.get('include_labels', False)
        include_labels_only = params.get('include_labels_only', False)
        query = params.get("query")
        dataview = self.get_object()
        xform = dataview.xform

        if include_labels is not None:
            include_labels = str_to_bool(include_labels)

        if include_labels_only is not None:
            include_labels_only = str_to_bool(include_labels_only)

        if include_hxl is not None:
            include_hxl = str_to_bool(include_hxl)

        remove_group_name = params.get('remove_group_name', False)
        columns_with_hxl = get_columns_with_hxl(xform.survey.get('children'))

        if columns_with_hxl and include_hxl:
            include_hxl = include_hxl_row(
                dataview.columns, list(columns_with_hxl)
            )

        options = {
            'remove_group_name': remove_group_name,
            'dataview_pk': dataview.pk,
            'include_hxl': include_hxl,
            'include_labels': include_labels,
            'include_labels_only': include_labels_only
        }
        if query:
            options.update({'query': query})

        if job_uuid:
            job = AsyncResult(job_uuid)
            if job.state == 'SUCCESS':
                export_id = job.result
                export = Export.objects.get(id=export_id)

                resp = export_async_export_response(request, export)
            else:
                resp = {
                    'job_status': job.state
                }

        else:
            resp = process_async_export(request, xform, export_type,
                                        options=options)

        return Response(data=resp,
                        status=status.HTTP_202_ACCEPTED,
                        content_type="application/json")

    @action(methods=['GET'], detail=True)
    def form(self, request, format='json', **kwargs):
        dataview = self.get_object()
        xform = dataview.xform
        if format not in ['json', 'xml', 'xls']:
            return HttpResponseBadRequest('400 BAD REQUEST',
                                          content_type='application/json',
                                          status=400)
        filename = xform.id_string + "." + format
        response = response_for_format(xform, format=format)
        response['Content-Disposition'] = 'attachment; filename=' + filename

        return response

    @action(methods=['GET'], detail=True)
    def form_details(self, request, *args, **kwargs):
        dataview = self.get_object()
        xform = dataview.xform
        serializer = XFormSerializer(xform, context={'request': request})

        return Response(data=serializer.data,
                        content_type="application/json")

    @action(methods=['GET'], detail=True)
    def charts(self, request, *args, **kwargs):
        dataview = self.get_object()
        xform = dataview.xform
        serializer = self.get_serializer(dataview)

        field_name = request.query_params.get('field_name')
        field_xpath = request.query_params.get('field_xpath')
        fmt = kwargs.get('format', request.accepted_renderer.format)
        group_by = request.query_params.get('group_by')

        if field_name:
            field = get_field_from_field_name(field_name, xform)
            field_xpath = field_name if isinstance(field, basestring) \
                else field.get_abbreviated_xpath()

        if field_xpath and field_xpath not in dataview.columns and \
                field_xpath not in [common_tags.SUBMISSION_TIME,
                                    common_tags.SUBMITTED_BY,
                                    common_tags.DURATION]:
            raise Http404(
                "Field %s does not not exist on the dataview" % field_name)

        if field_name or field_xpath:
            data = get_chart_data_for_field(
                field_name, xform, fmt, group_by, field_xpath,
                data_view=dataview
            )

            return Response(data, template_name='chart_detail.html')

        if fmt != 'json' and field_name is None:
            raise ParseError("Not supported")

        data = serializer.data
        data["fields"] = {}
        for field in xform.survey_elements:
            field_xpath = field.get_abbreviated_xpath()
            if field_xpath in dataview.columns:
                url = reverse('dataviews-charts', kwargs={'pk': dataview.pk},
                              request=request, format=fmt)
                field_url = get_form_field_chart_url(url, field.name)
                data["fields"][field.name] = field_url

        return Response(data)

    @action(methods=['GET'], detail=True)
    def xls_export(self, request, *args, **kwargs):
        dataview = self.get_object()
        xform = dataview.xform

        token = None
        export_type = "xls"
        query = request.query_params.get("query", {})
        meta = request.GET.get('meta')

        return custom_response_handler(request,
                                       xform,
                                       query,
                                       export_type,
                                       token,
                                       meta,
                                       dataview)

    def destroy(self, request, *args, **kwargs):
        dataview = self.get_object()
        user = request.user
        dataview.soft_delete(user)

        return Response(status=status.HTTP_204_NO_CONTENT)


def dataview_post_save_callback(sender, instance=None, created=False,
                                **kwargs):
    safe_delete('{}{}'.format(PROJECT_LINKED_DATAVIEWS, instance.project.pk))


def dataview_post_delete_callback(sender, instance, **kwargs):
    if instance.project:
        safe_delete('{}{}'.format(PROJECT_LINKED_DATAVIEWS,
                                  instance.project.pk))


post_save.connect(dataview_post_save_callback,
                  sender=DataView,
                  dispatch_uid='dataview_post_save_callback')

post_delete.connect(dataview_post_delete_callback,
                    sender=DataView,
                    dispatch_uid='dataview_post_delete_callback')
