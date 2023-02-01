# -*- coding: utf-8 -*-
"""
MergedXFormViewSet: API endpoint for /api/merged-datasets
"""

import json

from django.db.models import Sum
from django.http import HttpResponseBadRequest
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import Instance, MergedXForm
from onadata.libs import filters
from onadata.libs.renderers import renderers
from onadata.libs.serializers.merged_xform_serializer import MergedXFormSerializer
from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.libs.pagination import StandardPageNumberPagination


# pylint: disable=too-many-ancestors
class MergedXFormViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Merged XForms viewset: create, list, retrieve, destroy
    """

    filter_backends = (
        filters.AnonDjangoObjectPermissionFilter,
        filters.PublicDatasetsFilter,
    )
    permission_classes = [XFormPermissions]
    queryset = (
        MergedXForm.objects.filter(deleted_at__isnull=True)
        .annotate(number_of_submissions=Sum("xforms__num_of_submissions"))
        .all()
    )
    pagination_class = StandardPageNumberPagination
    serializer_class = MergedXFormSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.StaticXMLRenderer,
        renderers.GeoJsonRenderer,
    ]

    def get_serializer_class(self):
        """
        Get appropriate serializer class
        """
        export_type = self.kwargs.get("format")
        if self.action == "data" and export_type == "geojson":
            serializer_class = GeoJsonSerializer
        else:
            serializer_class = self.serializer_class

        return serializer_class

    def list(self, request, *args, **kwargs):
        """
        List endpoint for Merged XForms
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # pylint: disable=unused-argument
    @action(methods=["GET"], detail=True)
    def form(self, *args, **kwargs):
        """Return XForm JSON, XLS or XML representing"""

        fmt = kwargs["format"]
        if fmt not in ["json", "xml", "xls"]:
            return HttpResponseBadRequest(
                "400 BAD REQUEST", content_type="application/json", status=400
            )

        merged_xform = self.get_object()
        data = getattr(merged_xform, fmt)
        if fmt == "json":
            data = json.loads(data) if isinstance(data, str) else data

        return Response(data)

    # pylint: disable=unused-argument
    @action(methods=["GET"], detail=True)
    def data(self, request, *args, **kwargs):
        """Return data from the merged xforms"""
        merged_xform = self.get_object()
        export_type = self.kwargs.get("format", request.GET.get("format"))
        queryset = Instance.objects.filter(
            xform__in=merged_xform.xforms.all(),
            deleted_at__isnull=True
        ).order_by("pk")

        if export_type == "geojson":
            page = self.paginate_queryset(queryset)
            geojson_content_type = 'application/geo+json'
            serializer = serializer = self.get_serializer(page, many=True)
            return Response(serializer.data,
                            headers={'Content-Type': geojson_content_type})

        return Response(queryset.values_list("json", flat=True))
