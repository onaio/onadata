# -*- coding: utf-8 -*-
"""
The /data API endpoint.
"""
import json
import math
import types
from typing import Union

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.utils import DataError, OperationalError
from django.http import Http404, StreamingHttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _

import six
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import ModelViewSet

from onadata.libs.serializers.geojson_serializer import GeoJsonSerializer
from onadata.libs.pagination import CountOverridablePageNumberPagination

from onadata.apps.api.permissions import ConnectViewsetPermissions, XFormPermissions
from onadata.apps.api.tools import add_tags_to_instance, get_baseviewset_class
from onadata.apps.logger.models import MergedXForm, OsmData
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import FormInactiveError, Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.messaging.constants import SUBMISSION_DELETED, XFORM
from onadata.apps.messaging.serializers import send_message
from onadata.apps.viewer.models.parsed_instance import (
    get_etag_hash_from_query,
    get_sql_with_params,
    get_where_clause,
    query_data,
)
from onadata.libs import filters
from onadata.libs.data import parse_int, strtobool
from onadata.libs.exceptions import EnketoError, NoRecordsPermission
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin,
)
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.permissions import (
    CAN_DELETE_SUBMISSION,
    filter_queryset_xform_meta_perms,
    filter_queryset_xform_meta_perms_sql,
)
from onadata.libs.renderers import renderers
from onadata.libs.serializers.data_serializer import (
    DataInstanceSerializer,
    DataInstanceXMLSerializer,
    DataSerializer,
    InstanceHistorySerializer,
    JsonDataSerializer,
    OSMSerializer,
)
from onadata.libs.utils.api_export_tools import custom_response_handler
from onadata.libs.utils.common_tools import json_stream
from onadata.libs.utils.viewer_tools import get_enketo_urls, get_form_url

SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]
SUBMISSION_RETRIEVAL_THRESHOLD = getattr(
    settings, "SUBMISSION_RETRIEVAL_THRESHOLD", 10000
)

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()


def get_data_and_form(kwargs):
    """
    Checks if the dataid in ``kwargs`` is a valid integer.
    """
    data_id = str(kwargs.get("dataid"))
    if not data_id.isdigit():
        raise ParseError(_("Data ID should be an integer"))

    return (data_id, kwargs.get("format"))


def delete_instance(instance, user):
    """
    Function that calls Instance.set_deleted and catches any exception that may
     occur.
    :param instance:
    :param user:
    :return:
    """
    try:
        instance.set_deleted(timezone.now(), user)
    except FormInactiveError as e:
        raise ParseError(str(e)) from e


# pylint: disable=http-response-with-content-type-json
# pylint: disable=too-many-ancestors
class DataViewSet(
    AnonymousUserPublicFormsMixin,
    AuthenticateHeaderMixin,
    ETagsMixin,
    CacheControlMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    This endpoint provides access to submitted data.
    """

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [
        renderers.XLSRenderer,
        renderers.XLSXRenderer,
        renderers.CSVRenderer,
        renderers.CSVZIPRenderer,
        renderers.SAVZIPRenderer,
        renderers.InstanceXMLRenderer,
        renderers.SurveyRenderer,
        renderers.GeoJsonRenderer,
        renderers.KMLRenderer,
        renderers.OSMRenderer,
        renderers.FLOIPRenderer,
    ]

    filter_backends = (
        filters.AnonDjangoObjectPermissionFilter,
        filters.XFormOwnerFilter,
        filters.DataFilter,
    )
    serializer_class = DataSerializer
    permission_classes = (XFormPermissions,)
    lookup_field = "pk"
    lookup_fields = ("pk", "dataid")
    extra_lookup_fields = None
    data_count = None
    public_data_endpoint = "public"
    pagination_class = CountOverridablePageNumberPagination

    queryset = XForm.objects.filter(deleted_at__isnull=True)

    def get_serializer_class(self):
        """Returns appropriate serializer class based on context."""
        pk_lookup, dataid_lookup = self.lookup_fields
        form_pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)
        fmt = self.kwargs.get("format", self.request.GET.get("format"))
        sort = self.request.GET.get("sort")
        fields = self.request.GET.get("fields")
        if fmt == Attachment.OSM:
            serializer_class = OSMSerializer
        elif fmt == "geojson":
            serializer_class = GeoJsonSerializer
        elif fmt == "xml":
            serializer_class = DataInstanceXMLSerializer
        elif (
            form_pk is not None and
            dataid is None and
            form_pk != self.public_data_endpoint
        ):
            if sort or fields:
                serializer_class = JsonDataSerializer
            else:
                serializer_class = DataInstanceSerializer
        else:
            serializer_class = super().get_serializer_class()

        return serializer_class

    # pylint: disable=unused-argument
    def get_object(self, queryset=None):
        """Returns the appropriate object based on context."""
        obj = super().get_object()
        pk_lookup, dataid_lookup = self.lookup_fields
        form_pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)

        if form_pk is not None and dataid is not None:
            try:
                int(dataid)
            except ValueError as e:
                raise ParseError(_(f"Invalid dataid {dataid}")) from e

            if not obj.is_merged_dataset:
                obj = get_object_or_404(
                    Instance, pk=dataid, xform__pk=form_pk, deleted_at__isnull=True
                )
            else:
                xforms = obj.mergedxform.xforms.filter(deleted_at__isnull=True)
                pks = list(xforms.values_list("pk", flat=True))

                obj = get_object_or_404(
                    Instance, pk=dataid, xform_id__in=pks, deleted_at__isnull=True
                )

        return obj

    def _get_public_forms_queryset(self):
        return XForm.objects.filter(
            Q(shared=True) | Q(shared_data=True), deleted_at__isnull=True
        )

    def _filtered_or_shared_queryset(self, queryset, form_pk):
        filter_kwargs = {self.lookup_field: form_pk}
        queryset = queryset.filter(**filter_kwargs).only("id", "shared")

        if not queryset:
            filter_kwargs["shared_data"] = True
            queryset = XForm.objects.filter(**filter_kwargs).only("id", "shared")

            if not queryset:
                raise Http404(_("No data matches with given query."))

        return queryset

    # pylint: disable=unused-argument
    def filter_queryset(self, queryset, view=None):
        """Returns and filters queryset based on context and query params."""
        queryset = super().filter_queryset(queryset.only("id", "shared"))
        form_pk = self.kwargs.get(self.lookup_field)

        if form_pk:
            try:
                int(form_pk)
            except ValueError as e:
                if form_pk == self.public_data_endpoint:
                    queryset = self._get_public_forms_queryset()
                else:
                    raise ParseError(_(f"Invalid pk {form_pk}")) from e
            else:
                queryset = self._filtered_or_shared_queryset(queryset, form_pk)
        else:
            tags = self.request.query_params.get("tags")
            not_tagged = self.request.query_params.get("not_tagged")

            if tags and isinstance(tags, six.string_types):
                tags = tags.split(",")
                queryset = queryset.filter(tags__name__in=tags)
            if not_tagged and isinstance(not_tagged, six.string_types):
                not_tagged = not_tagged.split(",")
                queryset = queryset.exclude(tags__name__in=not_tagged)

        return queryset

    @action(
        methods=["GET", "POST", "DELETE"],
        detail=True,
        extra_lookup_fields=[
            "label",
        ],
    )
    def labels(self, request, *args, **kwargs):
        """
        Data labels API endpoint.
        """
        http_status = status.HTTP_400_BAD_REQUEST
        # pylint: disable=attribute-defined-outside-init
        self.object = instance = self.get_object()

        if request.method == "POST":
            add_tags_to_instance(request, instance)
            http_status = status.HTTP_201_CREATED

        tags = instance.tags
        label = kwargs.get("label")

        if request.method == "GET" and label:
            data = [tag["name"] for tag in tags.filter(name=label).values("name")]

        elif request.method == "DELETE" and label:
            count = tags.count()
            tags.remove(label)

            # Accepted, label does not exist hence nothing removed
            http_status = (
                status.HTTP_200_OK
                if count > tags.count()
                else status.HTTP_404_NOT_FOUND
            )

            data = list(tags.names())
        else:
            data = list(tags.names())

        if request.method == "GET":
            http_status = status.HTTP_200_OK

        setattr(self, "etag_data", data)

        return Response(data, status=http_status)

    @action(methods=["GET"], detail=True)
    def enketo(self, request, *args, **kwargs):
        """
        Data Enketo URLs endpoint
        """
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        data = {}
        if isinstance(self.object, XForm):
            raise ParseError(_("Data id not provided."))
        if isinstance(self.object, Instance):
            if request.user.has_perm("change_xform", self.object.xform):
                return_url = request.query_params.get("return_url")
                form_url = get_form_url(
                    request,
                    self.object.xform.user.username,
                    xform_pk=self.object.xform.id,
                )
                if not return_url:
                    raise ParseError(_("return_url not provided."))

                try:
                    data = get_enketo_urls(
                        form_url,
                        self.object.xform.id_string,
                        instance_id=self.object.uuid,
                        instance_xml=self.object.xml,
                        return_url=return_url,
                    )
                    if "edit_url" in data:
                        data["url"] = data.pop("edit_url")
                except EnketoError as e:
                    raise ParseError(str(e)) from e
            else:
                raise PermissionDenied(_("You do not have edit permissions."))

        setattr(self, "etag_data", data)

        return Response(data=data)

    def destroy(self, request, *args, **kwargs):
        """Soft deletes submissions data."""
        instance_ids = request.data.get("instance_ids")
        delete_all_submissions = strtobool(request.data.get("delete_all", "False"))
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()

        if isinstance(self.object, XForm):
            if not instance_ids and not delete_all_submissions:
                raise ParseError(_("Data id(s) not provided."))
            initial_count = self.object.submission_count()
            if delete_all_submissions:
                # Update timestamp only for active records
                queryset = self.object.instances.filter(deleted_at__isnull=True)
            else:
                instance_ids = [x for x in instance_ids.split(",") if x.isdigit()]
                if not instance_ids:
                    raise ParseError(_("Invalid data ids were provided."))

                queryset = self.object.instances.filter(
                    id__in=instance_ids,
                    xform=self.object,
                    # do not update this timestamp when the record have
                    # already been deleted.
                    deleted_at__isnull=True,
                )

            for instance in queryset.iterator():
                delete_instance(instance, request.user)

            # updates the num_of_submissions for the form.
            after_count = self.object.submission_count(force_update=True)
            number_of_records_deleted = initial_count - after_count

            # update the date modified field of the project
            self.object.project.date_modified = timezone.now()
            self.object.project.save(update_fields=["date_modified"])

            # send message
            send_message(
                instance_id=instance_ids,
                target_id=self.object.id,
                target_type=XFORM,
                user=request.user,
                message_verb=SUBMISSION_DELETED,
            )

            return Response(
                data={"message": f"{number_of_records_deleted} records were deleted"},
                status=status.HTTP_200_OK,
            )

        if isinstance(self.object, Instance):

            if request.user.has_perm(CAN_DELETE_SUBMISSION, self.object.xform):
                instance_id = self.object.pk
                delete_instance(self.object, request.user)

                # send message
                send_message(
                    instance_id=instance_id,
                    target_id=self.object.xform.id,
                    target_type=XFORM,
                    user=request.user,
                    message_verb=SUBMISSION_DELETED,
                )
            else:
                raise PermissionDenied(_("You do not have delete permissions."))

        return Response(status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request, *args, **kwargs):
        """Returns API data for the targeted object."""
        _data_id, _format = get_data_and_form(kwargs)
        # pylint: disable=attribute-defined-outside-init
        self.object = instance = self.get_object()

        if _format == "json" or _format is None or _format == "debug":
            return Response(instance.json)
        if _format == "xml":
            return Response(instance.xml)
        if _format == "geojson":
            return super().retrieve(request, *args, **kwargs)
        if _format == Attachment.OSM:
            serializer = self.get_serializer(instance.osm_data.all())

            return Response(serializer.data)

        raise ParseError(_(f"'{_format}' format unknown or not implemented!"))

    @action(methods=["GET"], detail=True)
    def history(self, request, *args, **kwargs):
        """
        Return submission history.
        """
        _data_id, _format = get_data_and_form(kwargs)
        instance = self.get_object()

        # retrieve all history objects and return them
        if _format == "json" or _format is None or _format == "debug":
            instance_history = instance.submission_history.all()
            serializer = InstanceHistorySerializer(instance_history, many=True)
            return Response(serializer.data)
        raise ParseError(_(f"'{_format}' format unknown or not implemented!"))

    # pylint: disable=too-many-locals,too-many-branches
    def _set_pagination_headers(
        self,
        xform: XForm,
        current_page: Union[int, str],
        current_page_size: Union[int, str] = SUBMISSION_RETRIEVAL_THRESHOLD,
    ):
        """
        Sets the self.headers value for the viewset
        """
        url = self.request.build_absolute_uri()
        query = self.request.query_params.get("query")
        base_url = url.split("?")[0]
        if query:
            num_of_records = self.object_list.count()
        else:
            num_of_records = xform.num_of_submissions
        next_page_url = None
        prev_page_url = None
        first_page_url = None
        last_page_url = None
        links = []

        if isinstance(current_page, str):
            try:
                current_page = int(current_page)
            except ValueError:
                return

        if isinstance(current_page_size, str):
            try:
                current_page_size = int(current_page_size)
            except ValueError:
                return

        if (current_page * current_page_size) < num_of_records:
            next_page_url = (
                f"{base_url}?page={current_page + 1}&" f"page_size={current_page_size}"
            )

        if current_page > 1:
            prev_page_url = (
                f"{base_url}?page={current_page - 1}" f"&page_size={current_page_size}"
            )

        last_page = math.ceil(num_of_records / current_page_size)
        if last_page not in (current_page, current_page + 1):
            last_page_url = f"{base_url}?page={last_page}&page_size={current_page_size}"

        if current_page != 1:
            first_page_url = f"{base_url}?page=1&page_size={current_page_size}"

        if not hasattr(self, "headers"):
            # pylint: disable=attribute-defined-outside-init
            self.headers = {}

        for rel, link in (
            ("prev", prev_page_url),
            ("next", next_page_url),
            ("last", last_page_url),
            ("first", first_page_url),
        ):
            if link:
                links.append(f'<{link}>; rel="{rel}"')
        self.headers.update({"Link": ", ".join(links)})

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def list(self, request, *args, **kwargs):
        """Returns list of data API endpoints for different forms."""
        fields = request.GET.get("fields")
        query = request.GET.get("query", {})
        sort = request.GET.get("sort")
        start = parse_int(request.GET.get("start"))
        limit = parse_int(request.GET.get("limit"))
        export_type = kwargs.get("format", request.GET.get("format"))
        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)
        is_public_request = lookup == self.public_data_endpoint

        if lookup_field not in list(kwargs):
            # pylint: disable=attribute-defined-outside-init
            self.object_list = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(self.object_list, many=True)

            return Response(serializer.data)

        if is_public_request:
            # pylint: disable=attribute-defined-outside-init
            self.object_list = self._get_public_forms_queryset()
        elif lookup:
            queryset = self.filter_queryset(self.get_queryset()).values_list(
                "pk", "is_merged_dataset"
            )
            xform_id, is_merged_dataset = queryset[0] if queryset else (lookup, False)
            pks = [xform_id]
            if is_merged_dataset:
                merged_form = MergedXForm.objects.get(pk=xform_id)
                queryset = merged_form.xforms.filter(
                    deleted_at__isnull=True
                ).values_list("id", "num_of_submissions")
                try:
                    pks, num_of_submissions = [list(value) for value in zip(*queryset)]
                    num_of_submissions = sum(num_of_submissions)
                except ValueError:
                    pks, num_of_submissions = [], 0
            else:
                num_of_submissions = XForm.objects.get(id=xform_id).num_of_submissions
            # pylint: disable=attribute-defined-outside-init
            self.object_list = Instance.objects.filter(
                xform_id__in=pks, deleted_at=None
            ).only("json")

            # Enable ordering for XForms with Submissions that are less
            # than the SUBMISSION_RETRIEVAL_THRESHOLD
            if num_of_submissions < SUBMISSION_RETRIEVAL_THRESHOLD:
                # pylint: disable=attribute-defined-outside-init
                self.object_list = self.object_list.order_by("id")

            xform = self.get_object()
            # pylint: disable=attribute-defined-outside-init
            self.object_list = filter_queryset_xform_meta_perms(
                xform, request.user, self.object_list
            )
            tags = self.request.query_params.get("tags")
            not_tagged = self.request.query_params.get("not_tagged")

            # pylint: disable=attribute-defined-outside-init
            self.object_list = filters.InstanceFilter(
                self.request.query_params, queryset=self.object_list, request=request
            ).qs

            if tags and isinstance(tags, six.string_types):
                tags = tags.split(",")
                self.object_list = self.object_list.filter(tags__name__in=tags)
            if not_tagged and isinstance(not_tagged, six.string_types):
                not_tagged = not_tagged.split(",")
                self.object_list = self.object_list.exclude(tags__name__in=not_tagged)

        if (
            export_type is None or export_type in ["json", "jsonp", "debug", "xml"]
        ) and hasattr(self, "object_list"):
            return self._get_data(query, fields, sort, start, limit, is_public_request)

        xform = self.get_object()
        kwargs = {"instance__xform": xform}

        if export_type == Attachment.OSM:
            if request.GET:
                self.set_object_list(
                    query, fields, sort, start, limit, is_public_request
                )
                kwargs = {"instance__in": self.object_list}
            osm_list = OsmData.objects.filter(**kwargs).order_by("instance")
            page = self.paginate_queryset(osm_list)
            serializer = self.get_serializer(page)

            return Response(serializer.data)

        if export_type is None or export_type in ["json"]:
            # perform default viewset retrieve, no data export
            return super().list(request, *args, **kwargs)

        if export_type == "geojson":
            # raise 404 if all instances dont have geoms
            if not xform.instances_with_geopoints and not (
                    xform.polygon_xpaths() or xform.geotrace_xpaths()):
                raise Http404(_("Not Found"))

            # add pagination when fetching geojson features
            page = self.paginate_queryset(self.object_list)
            serializer = self.get_serializer(page, many=True)

            return Response(serializer.data)

        return custom_response_handler(request, xform, query, export_type)

    # pylint: disable=too-many-arguments
    def set_object_list(self, query, fields, sort, start, limit, is_public_request):
        """
        Set the submission instances queryset.
        """
        try:
            enable_etag = True
            if not is_public_request:
                xform = self.get_object()
                self.data_count = xform.num_of_submissions
                enable_etag = self.data_count < SUBMISSION_RETRIEVAL_THRESHOLD

            where, where_params = get_where_clause(query)
            if where:
                # pylint: disable=attribute-defined-outside-init
                self.object_list = self.object_list.extra(
                    where=where, params=where_params
                )

            if (start and limit or limit) and (not sort and not fields):
                start = start if start is not None else 0
                limit = limit if start is None or start == 0 else start + limit
                # pylint: disable=attribute-defined-outside-init
                self.object_list = filter_queryset_xform_meta_perms(
                    self.get_object(), self.request.user, self.object_list
                )
                # pylint: disable=attribute-defined-outside-init
                self.object_list = self.object_list[start:limit]
            elif (sort or limit or start or fields) and not is_public_request:
                try:
                    query = filter_queryset_xform_meta_perms_sql(
                        self.get_object(), self.request.user, query
                    )
                    # pylint: disable=attribute-defined-outside-init
                    self.object_list = query_data(
                        xform,
                        query=query,
                        sort=sort,
                        start_index=start,
                        limit=limit,
                        fields=fields,
                        json_only=not self.kwargs.get("format") == "xml",
                    )
                except NoRecordsPermission:
                    # pylint: disable=attribute-defined-outside-init
                    self.object_list = []

            # ETags are Disabled for XForms with Submissions that surpass
            # the configured SUBMISSION_RETRIEVAL_THRESHOLD setting
            if enable_etag:
                if isinstance(self.object_list, QuerySet):
                    setattr(
                        self, "etag_hash", (get_etag_hash_from_query(self.object_list))
                    )
                else:
                    sql, params, records = get_sql_with_params(
                        xform,
                        query=query,
                        sort=sort,
                        start_index=start,
                        limit=limit,
                        fields=fields,
                    )
                    setattr(
                        self,
                        "etag_hash",
                        (get_etag_hash_from_query(records, sql, params)),
                    )
        except ValueError as e:
            raise ParseError(str(e)) from e
        except DataError as e:
            raise ParseError(str(e)) from e

    def paginate_queryset(self, queryset):
        """Returns a paginated queryset."""
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self, count=self.data_count
        )

    # pylint: disable=too-many-arguments,too-many-locals
    def _get_data(self, query, fields, sort, start, limit, is_public_request):
        self.set_object_list(query, fields, sort, start, limit, is_public_request)

        retrieval_threshold = getattr(settings, "SUBMISSION_RETRIEVAL_THRESHOLD", 10000)
        pagination_keys = [
            self.paginator.page_query_param,
            self.paginator.page_size_query_param,
        ]
        query_param_keys = self.request.query_params
        should_paginate = any(k in query_param_keys for k in pagination_keys)

        if not should_paginate and not is_public_request:
            # Paginate requests that try to retrieve data that surpasses
            # the submission retrieval threshold
            xform = self.get_object()
            num_of_submissions = xform.num_of_submissions
            should_paginate = num_of_submissions > retrieval_threshold
            if should_paginate:
                self.paginator.page_size = retrieval_threshold

        if not isinstance(self.object_list, types.GeneratorType) and should_paginate:
            current_page = query_param_keys.get(self.paginator.page_query_param, 1)
            current_page_size = query_param_keys.get(
                self.paginator.page_size_query_param, retrieval_threshold
            )

            self._set_pagination_headers(
                self.get_object(),
                current_page=current_page,
                current_page_size=current_page_size,
            )

            try:
                # pylint: disable=attribute-defined-outside-init
                self.object_list = self.paginate_queryset(self.object_list)
            except OperationalError:
                # pylint: disable=attribute-defined-outside-init
                self.object_list = self.paginate_queryset(self.object_list)

        stream_data = getattr(settings, "STREAM_DATA", False)
        if stream_data:
            response = self._get_streaming_response()
        else:
            serializer = self.get_serializer(self.object_list, many=True)
            response = Response(serializer.data, headers=self.headers)

        return response

    def _get_streaming_response(self):
        """
        Get a StreamingHttpResponse response object
        """

        def get_json_string(item):
            """Returns the ``item`` Instance instance as a JSON string."""
            return json.dumps(item.json if isinstance(item, Instance) else item)

        if self.kwargs.get("format") == "xml":
            response = StreamingHttpResponse(
                renderers.InstanceXMLRenderer().stream_data(
                    self.object_list, self.get_serializer
                ),
                content_type="application/xml",
            )
        else:
            response = StreamingHttpResponse(
                json_stream(self.object_list, get_json_string),
                content_type="application/json",
            )

        # calculate etag value and add it to response headers
        if hasattr(self, "etag_hash"):
            self.set_etag_header(None, self.etag_hash)

        # set headers on streaming response
        for k, v in self.headers.items():
            response[k] = v

        return response


# pylint: disable=too-many-ancestors
class AuthenticatedDataViewSet(DataViewSet):
    """
    Authenticated requests only.
    """

    permission_classes = (ConnectViewsetPermissions,)
