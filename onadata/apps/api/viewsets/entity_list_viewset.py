from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import (
    CreateModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    ListModelMixin,
)


from onadata.apps.api.permissions import EntityListPermission
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Entity, EntityList
from onadata.libs.filters import AnonUserEntityListFilter, EntityListProjectFilter
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.permissions import CAN_ADD_PROJECT_ENTITYLIST
from onadata.libs.serializers.entity_serializer import (
    EntityArraySerializer,
    EntitySerializer,
    EntityListSerializer,
    EntityListArraySerializer,
    EntityListDetailSerializer,
)


BaseViewset = get_baseviewset_class()

# pylint: disable=too-many-ancestors


class EntityListViewSet(
    CacheControlMixin,
    ETagsMixin,
    BaseViewset,
    GenericViewSet,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
):
    queryset = (
        EntityList.objects.filter(deleted_at__isnull=True)
        .order_by("pk")
        .prefetch_related(
            "registration_forms",
            "follow_up_forms",
        )
    )
    serializer_class = EntityListSerializer
    permission_classes = (EntityListPermission,)
    pagination_class = StandardPageNumberPagination
    filter_backends = (AnonUserEntityListFilter, EntityListProjectFilter)

    def get_serializer_class(self):
        """Override get_serializer_class"""
        if self.action == "list":
            return EntityListArraySerializer

        if self.action == "retrieve":
            return EntityListDetailSerializer

        if self.action == "entities":
            if self.kwargs.get("entity_pk") is None:
                return EntityArraySerializer

            return EntitySerializer

        return super().get_serializer_class()

    def get_serializer_context(self):
        """Override get_serializer_context"""
        context = super().get_serializer_context()

        if self.action == "entities":
            context.update({"entity_list": self.get_object()})

        return context

    @action(
        methods=["GET", "PUT", "PATCH", "DELETE"],
        detail=True,
        url_path="entities(?:/(?P<entity_pk>[^/.]+))?",
    )
    def entities(self, request, *args, **kwargs):
        """Provides `list`, `retrieve` `update` and `destroy` actions for Entities"""
        entity_list = self.get_object()
        entity_pk = kwargs.get("entity_pk")

        if entity_pk:
            method = request.method.upper()
            entity = get_object_or_404(Entity, pk=entity_pk, deleted_at__isnull=True)

            if method == "DELETE":
                entity.soft_delete(request.user)

                return Response(status=status.HTTP_204_NO_CONTENT)

            if method in ["PUT", "PATCH"]:
                serializer = self.get_serializer(entity, data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save()

                return Response(serializer.data)

            serializer = self.get_serializer(entity)

            return Response(serializer.data)

        entity_qs = (
            Entity.objects.filter(
                entity_list=entity_list,
                deleted_at__isnull=True,
            )
            # To improve performance, we specify only the column(s)
            # we are interested in using .only
            .only("json").order_by("pk")
        )
        page = self.paginate_queryset(entity_qs)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(entity_qs, many=True)

        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Override perform_detroy"""
        instance.soft_delete(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.validated_data["project"]

        if not self.request.user.has_perm(CAN_ADD_PROJECT_ENTITYLIST, project):
            return Response(status=status.HTTP_403_FORBIDDEN)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )
