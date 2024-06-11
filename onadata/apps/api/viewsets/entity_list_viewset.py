from django.shortcuts import get_object_or_404

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet


from onadata.apps.api.permissions import EntityListPermission
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Entity, EntityList
from onadata.libs.filters import EntityListProjectFilter
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.entity_serializer import (
    EntitySerializer,
    EntityListSerializer,
    EntityListDetailSerializer,
)


BaseViewset = get_baseviewset_class()

# pylint: disable=too-many-ancestors


class EntityListViewSet(
    CacheControlMixin,
    ETagsMixin,
    BaseViewset,
    ReadOnlyModelViewSet,
):
    queryset = EntityList.objects.all().order_by("pk")
    serializer_class = EntityListSerializer
    permission_classes = (EntityListPermission,)
    pagination_class = StandardPageNumberPagination
    filter_backends = (EntityListProjectFilter,)

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.request and self.request.user.is_anonymous:
            queryset = queryset.filter(project__shared=True)

        if self.action == "retrieve":
            # Prefetch related objects to be rendered for performance
            # optimization
            return queryset.prefetch_related(
                "registration_forms",
                "follow_up_forms",
            )

        return queryset

    def get_serializer_class(self):
        """Override get_serializer_class"""
        if self.action == "retrieve":
            return EntityListDetailSerializer

        if self.action == "entities":
            return EntitySerializer

        return super().get_serializer_class()

    @action(methods=["GET", "PUT", "PATCH"], detail=True)
    def entities(self, request, *args, **kwargs):
        """Returns a list of Entities for a single EntityList"""
        entity_list = self.get_object()
        entity_pk = kwargs.get("entity_pk")

        if entity_pk and request.method.upper() in ["PUT", "PATCH"]:
            entity = get_object_or_404(Entity, pk=entity_pk, deleted_at__isnull=True)
            serializer = self.get_serializer(
                entity,
                data=request.data,
                context={
                    **self.get_serializer_context(),
                    "entity_list": entity_list,
                },
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data)

        entities_qs = (
            Entity.objects.filter(
                entity_list=entity_list,
                deleted_at__isnull=True,
            )
            # To improve performance, we specify only the column(s)
            # we are interested in using .only
            .only("json").order_by("pk")
        )
        queryset = self.filter_queryset(entities_qs)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)
