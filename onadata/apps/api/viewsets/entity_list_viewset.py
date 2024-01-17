from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet


from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Entity, EntityList
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.anon_user_public_entity_lists_mixin import (
    AnonymousUserPublicEntityListsMixin,
)
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.serializers.entity_serializer import (
    EntitySerializer,
    EntityListSerializer,
    EntityListDetailSerializer,
)


BaseViewset = get_baseviewset_class()

# pylint: disable=too-many-ancestors


class EntityListViewSet(
    AnonymousUserPublicEntityListsMixin,
    CacheControlMixin,
    ETagsMixin,
    BaseViewset,
    ReadOnlyModelViewSet,
):
    queryset = EntityList.objects.all().order_by("pk")
    serializer_class = EntityListSerializer
    permission_classes = (AllowAny,)
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        """Override get_serializer_class"""
        if self.action == "retrieve":
            return EntityListDetailSerializer

        if self.action == "entities":
            return EntitySerializer

        return super().get_serializer_class()

    @action(methods=["GET"], detail=True)
    def entities(self, request, *args, **kwargs):
        """Returns a list of Entities"""
        entity_list = self.get_object()
        entities_qs = Entity.objects.filter(
            registration_form__entity_list=entity_list
        ).order_by("pk")
        page = self.paginate_queryset(entities_qs)
        serializer = self.get_serializer(page, many=True)

        return Response(serializer.data)
