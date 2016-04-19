import os

from rest_framework.authentication import BasicAuthentication
from rest_framework.settings import api_settings
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.apps.viewer.models.export import Export
from onadata.libs.renderers import renderers
from onadata.libs.serializers.export_serializer import ExportSerializer
from onadata.libs.authentication import (
    DigestAuthentication,
    TempTokenAuthentication,
    TempTokenURLParameterAuthentication)
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name


class ExportViewSet(ReadOnlyModelViewSet):
    authentication_classes = (DigestAuthentication,
                              TempTokenAuthentication,
                              TempTokenURLParameterAuthentication,
                              BasicAuthentication)
    queryset = Export.objects.filter()
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.OSMExportRenderer,
        renderers.ZipRenderer
    ]
    serializer_class = ExportSerializer

    def retrieve(self, request, pk=None):
        export = Export.objects.get(pk=pk)
        filename, extension = os.path.splitext(export.filename)
        extension = extension[1:]

        return response_with_mimetype_and_name(
            Export.EXPORT_MIMES[extension],
            filename,
            extension=extension,
            file_path=export.filepath,
            show_date=False)
