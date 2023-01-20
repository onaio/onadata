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
from onadata.libs.pagination import CountOverridablePageNumberPagination
from onadata.apps.logger.models import Instance, MergedXForm
from onadata.libs import filters
from onadata.libs.renderers import renderers
from onadata.libs.serializers.merged_xform_serializer import MergedXFormSerializer
from onadata.libs.utils.api_export_tools import custom_response_handler


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
    serializer_class = MergedXFormSerializer

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.StaticXMLRenderer,
        renderers.GeoJsonRenderer,
    ]

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
        export_type = self.kwargs.get("format", request.GET.get("format"))
        merged_xform = self.get_object()
        queryset = Instance.objects.filter(
            xform__in=merged_xform.xforms.all(),
            deleted_at__isnull=True
        ).order_by("pk")

        paginated_queryset = CountOverridablePageNumberPagination(
        ).paginate_queryset(queryset, request, self)

        if export_type == "geojson":
            extra_data = {
                "data_geo_field": request.GET.get("geo_field"),
                "data_fields": request.GET.get("fields"),
                "query": None
            }
            return custom_response_handler(
                request, merged_xform, None, export_type,
                instances_query_set=paginated_queryset,
                extra_data=extra_data)

        return Response(queryset.values_list("json", flat=True))
