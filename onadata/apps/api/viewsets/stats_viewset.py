# -*- coding: utf-8 -*-
"""
The /api/v1/stats API endpoint implementaion.
"""
from rest_framework import viewsets

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models.xform import XForm
from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin,
)
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.stats_serializer import (
    StatsInstanceSerializer,
    StatsSerializer,
)

BaseViewset = get_baseviewset_class()


# pylint: disable=too-many-ancestors
class StatsViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    AnonymousUserPublicFormsMixin,
    BaseViewset,
    viewsets.ReadOnlyModelViewSet,
):
    """
    The /api/v1/stats API endpoint implementaion.
    """

    lookup_field = "pk"
    queryset = XForm.objects.all()
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    permission_classes = [
        XFormPermissions,
    ]
    serializer_class = StatsSerializer

    def get_serializer_class(self):
        lookup = self.kwargs.get(self.lookup_field)
        if lookup is not None:
            return StatsInstanceSerializer

        return super().get_serializer_class()
