from celery.result import AsyncResult

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.settings import api_settings
from rest_framework import status

from onadata.apps.api.viewsets.xform_viewset import custom_response_handler
from onadata.apps.api.viewsets.xform_viewset import \
    _export_async_export_response
from onadata.apps.api.viewsets.xform_viewset import process_async_export
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.permissions import DataViewViewsetPermissions
from onadata.libs.renderers import renderers
from onadata.apps.viewer.models.export import Export
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.serializers.data_serializer import JsonDataSerializer
from onadata.libs.utils.export_tools import str_to_bool


class DataViewViewSet(ModelViewSet):
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
    ]

    def get_serializer_class(self):
        if self.action == 'data':
            serializer_class = JsonDataSerializer
        else:
            serializer_class = self.serializer_class

        return serializer_class

    @action(methods=['GET'])
    def data(self, request, format='json', **kwargs):
        """ Retrieve the data from the xform using this dataview """
        start = request.GET.get("start")
        limit = request.GET.get("limit")
        count = request.GET.get("count")
        export_type = self.kwargs.get('format', request.GET.get("format"))
        self.object = self.get_object()

        if export_type is None or export_type in ['json']:
            data = DataView.query_data(self.object, start, limit,
                                       str_to_bool(count))
            if 'error' in data:
                raise ParseError(data.get('error'))

            serializer = self.get_serializer(data, many=True)

            return Response(serializer.data)

        else:
            return custom_response_handler(request, self.object.xform, None,
                                           export_type, dataview=self.object)

    @action(methods=['GET'])
    def export_async(self, request, *args, **kwargs):
        job_uuid = request.QUERY_PARAMS.get('job_uuid')
        export_type = request.QUERY_PARAMS.get('format')
        dataview = self.get_object()
        xform = dataview.xform

        remove_group_name = request.QUERY_PARAMS.get('remove_group_name')

        options = {
            'remove_group_name': remove_group_name,
            'dataview_pk': dataview.pk
        }

        if job_uuid:
            job = AsyncResult(job_uuid)
            if job.state == 'SUCCESS':
                export_id = job.result
                export = Export.objects.get(id=export_id)

                resp = _export_async_export_response(request, xform, export,
                                                     dataview_pk=dataview.pk)
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
