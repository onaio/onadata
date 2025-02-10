# -*- coding: utf-8 -*-
"""
FloipViewSet: API endpoint for /api/floip
"""
from uuid import UUID

from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_json_api.pagination import PageNumberPagination
from rest_framework_json_api.parsers import JSONParser
from rest_framework_json_api.renderers import JSONRenderer

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import Instance, XForm
from onadata.libs import filters
from onadata.libs.renderers.renderers import floip_list
from onadata.libs.serializers.floip_serializer import (
    FloipListSerializer,
    FloipSerializer,
    FlowResultsResponseSerializer,
)


class FlowResultsJSONRenderer(JSONRenderer):
    """
    Render JSON API format with uuid.
    """

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    @classmethod
    def build_json_resource_obj(
        cls,
        fields,
        resource,
        resource_instance,
        resource_name,
        serializer,
        force_type_resolution=False,
    ):
        """
        Build a JSON resource object using the id as it appears in the
        resource.
        """
        obj = super().build_json_resource_obj(
            fields,
            resource,
            resource_instance,
            resource_name,
            serializer,
            force_type_resolution,
        )
        obj["id"] = resource["id"]

        return obj


# pylint: disable=too-many-ancestors
class FloipViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    FloipViewSet: create, list, retrieve, destroy
    """

    filter_backends = (
        filters.AnonDjangoObjectPermissionFilter,
        filters.PublicDatasetsFilter,
    )
    permission_classes = [XFormPermissions]
    queryset = XForm.objects.filter(deleted_at__isnull=True)
    serializer_class = FloipSerializer

    pagination_class = PageNumberPagination
    parser_classes = (JSONParser,)
    renderer_classes = (FlowResultsJSONRenderer,)

    lookup_field = "uuid"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        uuid = self.kwargs.get(self.lookup_field)
        uuid = UUID(uuid, version=4)
        obj = get_object_or_404(queryset, Q(uuid=uuid.hex) | Q(uuid=str(uuid)))
        self.check_object_permissions(self.request, obj)

        if self.request.user.is_anonymous and obj.require_auth:
            self.permission_denied(self.request)
        return obj

    def get_serializer_class(self):
        if self.action == "list":
            return FloipListSerializer

        if self.action == "responses":
            return FlowResultsResponseSerializer

        return super().get_serializer_class()

    def get_success_headers(self, data):
        headers = super().get_success_headers(data)
        headers["Content-Type"] = "application/vnd.api+json"
        uuid = str(UUID(data["id"]))
        headers["Location"] = self.request.build_absolute_uri(
            reverse("flow-results-detail", kwargs={"uuid": uuid})
        )

        return headers

    @action(methods=["GET", "POST"], detail=True)
    def responses(self, request, uuid=None):
        """
        Flow Results Responses endpoint.
        """
        status_code = status.HTTP_200_OK
        xform = self.get_object()
        uuid = str(UUID(uuid or xform.uuid, version=4))
        data = {"id": uuid, "type": "flow-results-data", "attributes": {}}
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Location": self.request.build_absolute_uri(
                reverse("flow-results-responses", kwargs={"uuid": uuid})
            ),
        }  # yapf: disable
        if request.method == "POST":
            serializer = FlowResultsResponseSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            data["response"] = serializer.data["responses"]
            if serializer.data["duplicates"]:
                status_code = status.HTTP_202_ACCEPTED
            else:
                status_code = status.HTTP_201_CREATED
        else:
            if xform.is_merged_dataset:
                pks = xform.mergedxform.xforms.filter(
                    deleted_at__isnull=True
                ).values_list("pk", flat=True)
                queryset = Instance.objects.filter(
                    xform_id__in=pks, deleted_at__isnull=True
                ).values_list("json", flat=True)
            else:
                queryset = xform.instances.values_list("json", flat=True)

            paginate_queryset = self.paginate_queryset(queryset)
            if paginate_queryset:
                data["attributes"]["responses"] = floip_list(paginate_queryset)
                response = self.get_paginated_response(data)
                for key, value in headers.items():
                    response[key] = value

                return response

            data["attributes"]["responses"] = floip_list(queryset)

        return Response(data, headers=headers, status=status_code)
