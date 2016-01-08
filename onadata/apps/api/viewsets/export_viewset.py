import os

from onadata.apps.viewer.models.export import Export
from onadata.libs.serializers.export_serializer import ExportSerializer
from onadata.libs.authentication import *
from rest_framework.authentication import (
    BasicAuthentication,
    TokenAuthentication)
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name


class ExportViewSet(ModelViewSet):
    authentication_classes = (DigestAuthentication,
                              TokenAuthentication,
                              TempTokenURLParameterAuthentication,
                              BasicAuthentication)
    queryset = Export.objects.filter()
    serializer_class = ExportSerializer

    def retrieve(self, request, pk=None):
        export = Export.objects.get(pk=pk)
        extension = os.path.splitext(export.filename)[1][1:]

        return response_with_mimetype_and_name(
            Export.EXPORT_MIMES[extension],
            export.filename,
            extension=extension,
            file_path=export.filepath)
