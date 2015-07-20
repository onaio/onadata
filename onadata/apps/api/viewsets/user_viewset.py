from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.generics import get_object_or_404
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import filters

from onadata.libs.filters import UserNoOrganizationsFilter
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.user_serializer import UserSerializer
from onadata.apps.api import permissions


class UserViewSet(AuthenticateHeaderMixin,
                  CacheControlMixin, ETagsMixin, ReadOnlyModelViewSet):
    """
    This endpoint allows you to list and retrieve user's first and last names.
    """
    queryset = User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.UserViewSetPermissions]
    filter_backends = (filters.SearchFilter, UserNoOrganizationsFilter,)
    search_fields = ('=email',)

    def get_object(self, queryset=None):
        """Lookup a  username by pk else use lookup_field"""
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        lookup = self.kwargs.get(self.lookup_field)
        filter_kwargs = {self.lookup_field: lookup}

        try:
            pk = int(lookup)
        except ValueError:
            pass
        else:
            filter_kwargs = {'pk': pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
