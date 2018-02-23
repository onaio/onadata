# -*- coding=utf-8 -*-
"""
Users /users API endpoint.
"""
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
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()  # pylint: disable=invalid-name


# pylint: disable=too-many-ancestors
class UserViewSet(AuthenticateHeaderMixin, BaseViewset, CacheControlMixin,
                  ETagsMixin, ReadOnlyModelViewSet):
    """
    This endpoint allows you to list and retrieve user's first and last names.
    """
    queryset = User.objects.filter(is_active=True).exclude(
        username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME, )
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.UserViewSetPermissions]
    filter_backends = (filters.SearchFilter, UserNoOrganizationsFilter, )
    search_fields = ('=email', )

    def get_object(self):
        """Lookup a  username by pk else use lookup_field"""
        queryset = self.filter_queryset(self.get_queryset())

        username = self.kwargs.get(self.lookup_field)
        filter_kwargs = {self.lookup_field: username}

        try:
            user_id = int(username)
        except ValueError:
            filter_kwargs = {'%s__iexact' % self.lookup_field: username}
        else:
            filter_kwargs = {'pk': user_id}

        user = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, user)

        return user
