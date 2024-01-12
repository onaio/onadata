from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import EntityList
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.anon_user_public_entity_lists_mixin import (
    AnonymousUserPublicEntityListsMixin,
)
from onadata.libs.serializers.entity_serializer import EntityListSerializer


BaseViewset = get_baseviewset_class()


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
