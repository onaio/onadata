# -*- coding: utf-8 -*-
"""
The /dataview API endpoint implementation.
"""

from django.db.models.signals import post_delete, post_save
from django.http import Http404, HttpResponseBadRequest
from django.utils.translation import gettext as _

from celery.result import AsyncResult
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.apps.api.permissions import DataViewViewsetPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.viewer.models.export import Export
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers import renderers
from onadata.libs.serializers.data_serializer import JsonDataSerializer
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.utils import common_tags
from onadata.libs.utils.common_tools import get_abbreviated_xpath
from onadata.libs.utils.api_export_tools import (
    custom_response_handler,
    export_async_export_response,
    process_async_export,
    response_for_format,
)
from onadata.libs.utils.cache_tools import (
    PROJECT_LINKED_DATAVIEWS,
    PROJ_OWNER_CACHE,
    safe_delete,
)
from onadata.libs.utils.chart_tools import (
    get_chart_data_for_field,
    get_field_from_field_name,
)
from onadata.libs.utils.export_tools import str_to_bool, parse_request_export_options

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()


def get_form_field_chart_url(url, field):
    """
    Returns a chart's ``url`` with the field_name ``field`` parameter appended to it.
    """
    return f"{url}?field_name={field}"


def filter_to_field_lookup(filter_string):
    """
    Converts a =, < or > to a django field lookup
    """
    if filter_string == "=":
        return "__iexact"
    if filter_string == "<":
        return "__lt"
    return "__gt"


def get_field_lookup(column, filter_string):
    """
    Convert filter_string + column into a field lookup expression
    """
    return "json__" + column + filter_to_field_lookup(filter_string)


def get_filter_kwargs(filters):
    """
    Apply filters on a queryset
    """
    kwargs = {}
    if filters:
        for f in filters:
            value = f"{f['value']}"
            column = f["column"]
            filter_kwargs = {get_field_lookup(column, f["filter"]): value}
            kwargs = {**kwargs, **filter_kwargs}
    return kwargs


def apply_filters(instance_qs, filters):
    """
    Apply filters on a queryset
    """
    if filters:
        return instance_qs.filter(**get_filter_kwargs(filters))
    return instance_qs


def get_dataview_instances(dataview):
    """
    Get all instances that belong to ths dataview
    """
    return apply_filters(
        dataview.xform.instances.filter(deleted_at__isnull=True), dataview.query
    )


# pylint: disable=too-many-ancestors
class DataViewViewSet(
    AuthenticateHeaderMixin, CacheControlMixin, ETagsMixin, BaseViewset, ModelViewSet
):
    """
    A simple ViewSet for viewing and editing DataViews.
    """

    queryset = DataView.objects.filter(deleted_at__isnull=True).select_related()
    serializer_class = DataViewSerializer
    permission_classes = [DataViewViewsetPermissions]
    lookup_field = "pk"
    pagination_class = StandardPageNumberPagination
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.ZipRenderer,
        renderers.GeoJsonRenderer,
    ]

    def get_serializer_class(self):
        """
        Get a serializer class based on request format
        """
        export_type = self.kwargs.get("format")
        if self.action == "data" and export_type == "geojson":
            serializer_class = GeoJsonSerializer
        elif self.action == "data":
            serializer_class = JsonDataSerializer
        else:
            serializer_class = self.serializer_class

        return serializer_class

    def list(self, request, *args, **kwargs):
        """
        List endpoint for Filtered datasets
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # pylint: disable=redefined-builtin,unused-argument
    @action(methods=["GET"], detail=True)
    def data(self, request, format="json", **kwargs):
        """Retrieve the data from the xform using this dataview"""
        start = request.GET.get("start")
        limit = request.GET.get("limit")
        count = request.GET.get("count")
        sort = request.GET.get("sort")
        query = request.GET.get("query")
        export_type = self.kwargs.get("format", request.GET.get("format"))
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        if export_type is None or export_type in ["json", "debug"]:
            data = DataView.query_data(
                self.object,
                start,
                limit,
                str_to_bool(count),
                sort=sort,
                filter_query=query,
            )
            if "error" in data:
                raise ParseError(data.get("error"))

            serializer = self.get_serializer(data, many=True)

            return Response(serializer.data)

        if export_type == "geojson":
            page = self.paginate_queryset(get_dataview_instances(self.object))

            serializer = self.get_serializer(page, many=True)
            geojson_content_type = "application/geo+json"
            return Response(
                serializer.data, headers={"Content-Type": geojson_content_type}
            )

        return custom_response_handler(
            request, self.object.xform, query, export_type, dataview=self.object
        )

    # pylint: disable=too-many-locals
    @action(methods=["GET"], detail=True)
    def export_async(self, request, *args, **kwargs):
        """Initiate's exports asynchronously."""
        params = request.query_params
        job_uuid = params.get("job_uuid")
        export_type = params.get("format")
        query = params.get("query")
        dataview = self.get_object()
        xform = dataview.xform
        options = parse_request_export_options(params)
        options["host"] = request.get_host()

        options.update(
            {
                "dataview_pk": dataview.pk,
            }
        )
        if query:
            options.update({"query": query})

        if job_uuid:
            job = AsyncResult(job_uuid)
            if job.state == "SUCCESS":
                export_id = job.result
                export = Export.objects.get(id=export_id)

                resp = export_async_export_response(request, export)
            else:
                resp = {"job_status": job.state}

        else:
            resp = process_async_export(request, xform, export_type, options=options)

        return Response(
            data=resp, status=status.HTTP_202_ACCEPTED, content_type="application/json"
        )

    # pylint: disable=redefined-builtin,unused-argument
    @action(methods=["GET"], detail=True)
    def form(self, request, format="json", **kwargs):
        """Returns the form as either json, xml or XLS linked the dataview."""
        dataview = self.get_object()
        xform = dataview.xform
        if format not in ["json", "xml", "xls"]:
            return HttpResponseBadRequest(
                "400 BAD REQUEST", content_type="application/json", status=400
            )
        filename = xform.id_string + "." + format
        response = response_for_format(xform, format=format)
        response["Content-Disposition"] = "attachment; filename=" + filename

        return response

    @action(methods=["GET"], detail=True)
    def form_details(self, request, *args, **kwargs):
        """Returns the dataview's form API data."""
        dataview = self.get_object()
        xform = dataview.xform
        serializer = XFormSerializer(xform, context={"request": request})

        return Response(data=serializer.data, content_type="application/json")

    @action(methods=["GET"], detail=True)
    def charts(self, request, *args, **kwargs):
        """Returns the charts data for the given dataview."""
        dataview = self.get_object()
        xform = dataview.xform
        serializer = self.get_serializer(dataview)

        field_name = request.query_params.get("field_name")
        field_xpath = request.query_params.get("field_xpath")
        fmt = kwargs.get("format", request.accepted_renderer.format)
        group_by = request.query_params.get("group_by")

        if field_name:
            field = get_field_from_field_name(field_name, xform)
            field_xpath = (
                field_name
                if isinstance(field, str)
                else get_abbreviated_xpath(field.get_xpath())
            )

        if (
            field_xpath
            and field_xpath not in dataview.columns
            and field_xpath
            not in [
                common_tags.SUBMISSION_TIME,
                common_tags.SUBMITTED_BY,
                common_tags.DURATION,
            ]
        ):
            raise Http404(_(f"Field {field_name} does not not exist on the dataview"))

        if field_name or field_xpath:
            data = get_chart_data_for_field(
                field_name, xform, fmt, group_by, field_xpath, data_view=dataview
            )

            return Response(data, template_name="chart_detail.html")

        if fmt != "json" and field_name is None:
            raise ParseError("Not supported")

        data = serializer.data
        data["fields"] = {}
        for field in xform.survey_elements:
            field_xpath = get_abbreviated_xpath(field.get_xpath())
            if field_xpath in dataview.columns:
                url = reverse(
                    "dataviews-charts",
                    kwargs={"pk": dataview.pk},
                    request=request,
                    format=fmt,
                )
                field_url = get_form_field_chart_url(url, field.name)
                data["fields"][field.name] = field_url

        return Response(data)

    @action(methods=["GET"], detail=True)
    def xlsx_export(self, request, *args, **kwargs):
        """Returns the data views XLS export files."""
        dataview = self.get_object()
        xform = dataview.xform

        token = None
        export_type = "xlsx"
        query = request.query_params.get("query", {})
        meta = request.GET.get("meta")

        return custom_response_handler(
            request, xform, query, export_type, token, meta, dataview
        )

    def destroy(self, request, *args, **kwargs):
        """Soft deletes the the dataview."""
        dataview = self.get_object()
        user = request.user
        dataview.soft_delete(user)
        safe_delete(f"{PROJ_OWNER_CACHE}{dataview.project.pk}")

        return Response(status=status.HTTP_204_NO_CONTENT)


# pylint: disable=unused-argument
def dataview_post_save_callback(sender, instance=None, created=False, **kwargs):
    """Clear project cache post dataview save."""
    safe_delete(f"{PROJECT_LINKED_DATAVIEWS}{instance.project.pk}")


def dataview_post_delete_callback(sender, instance, **kwargs):
    """Clear project cache post dataview delete."""
    if instance.project:
        safe_delete(f"{PROJECT_LINKED_DATAVIEWS}{instance.project.pk}")


post_save.connect(
    dataview_post_save_callback,
    sender=DataView,
    dispatch_uid="dataview_post_save_callback",
)

post_delete.connect(
    dataview_post_delete_callback,
    sender=DataView,
    dispatch_uid="dataview_post_delete_callback",
)
