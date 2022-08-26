# -*- coding: utf-8 -*-
"""
The /api/v1/exports API implementation.

List, Create, Update, Destroy Export model objects.
"""
import os

from rest_framework.mixins import DestroyModelMixin
from rest_framework.settings import api_settings
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.apps.api.permissions import ExportDjangoObjectPermission
from onadata.apps.viewer.models.export import Export
from onadata.libs import filters
from onadata.libs.authentication import TempTokenURLParameterAuthentication
from onadata.libs.renderers import renderers
from onadata.libs.serializers.export_serializer import ExportSerializer
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name


# pylint: disable=too-many-ancestors
class ExportViewSet(DestroyModelMixin, ReadOnlyModelViewSet):
    """
    The /api/v1/exports API implementation.

    List, Create, Update, Destroy Export model objects.
    """

    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES + [
        TempTokenURLParameterAuthentication
    ]
    queryset = Export.objects.all()
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.KMLRenderer,
        renderers.OSMExportRenderer,
        renderers.SAVZIPRenderer,
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.ZipRenderer,
    ]
    serializer_class = ExportSerializer
    filter_backends = (filters.ExportFilter,)
    permission_classes = [ExportDjangoObjectPermission]

    def retrieve(self, request, *args, **kwargs):
        export = self.get_object()
        filename, extension = os.path.splitext(export.filename)
        extension = extension[1:]

        return response_with_mimetype_and_name(
            Export.EXPORT_MIMES[extension],
            filename,
            extension=extension,
            file_path=export.filepath,
            show_date=False,
        )
