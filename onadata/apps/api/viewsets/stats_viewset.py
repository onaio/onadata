from rest_framework import viewsets

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models.xform import XForm

from onadata.libs import filters
from onadata.libs.mixins.anonymous_user_public_forms_mixin import (
    AnonymousUserPublicFormsMixin)
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.stats_serializer import (
    StatsSerializer, StatsInstanceSerializer)


class StatsViewSet(AuthenticateHeaderMixin,
                   CacheControlMixin,
                   ETagsMixin,
                   AnonymousUserPublicFormsMixin,
                   viewsets.ReadOnlyModelViewSet):

    lookup_field = 'pk'
    queryset = XForm.objects.all()
    filter_backends = (filters.AnonDjangoObjectPermissionFilter, )
    permission_classes = [XFormPermissions, ]
    serializer_class = StatsSerializer

    def get_serializer_class(self):
        lookup = self.kwargs.get(self.lookup_field)
        if lookup is not None:
            serializer_class = StatsInstanceSerializer
        else:
            serializer_class = \
                super(StatsViewSet, self).get_serializer_class()

        return serializer_class
