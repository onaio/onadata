import json

from django.conf import settings

from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.user_profile_serializer import\
    UserProfileSerializer
from onadata.apps.main.models import UserProfile
from onadata.apps.api.permissions import UserProfilePermissions


def replace_key_value(k, v, expected_dict):
    for a, b in expected_dict.items():
        if k == a:
            if isinstance(b, dict) and isinstance(v, dict):
                b.update(v)
            else:
                expected_dict[a] = v
        elif isinstance(b, dict):
            expected_dict[a] = replace_key_value(k, v, b)
    return expected_dict


def check_if_key_exists(k, expected_dict):
    for a, b in expected_dict.items():
        if a == k:
            return True
        elif isinstance(b, dict):
            return check_if_key_exists(k, b)
        elif isinstance(b, list):
            for c in b:
                if isinstance(c, dict):
                    return check_if_key_exists(k, c)
    return False


class UserProfileViewSet(AuthenticateHeaderMixin,
                         CacheControlMixin, ETagsMixin,
                         ObjectLookupMixin, ModelViewSet):
    """
    List, Retrieve, Update, Create/Register users.
    """
    queryset = UserProfile.objects.select_related().exclude(
        user__pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserProfileSerializer
    lookup_field = 'user'
    permission_classes = [UserProfilePermissions]
    ordering = ('user__username', )

    def get_object(self, queryset=None):
        """Lookup user profile by pk or username"""
        if self.kwargs.get(self.lookup_field, None) is None:
            raise ParseError(
                'Expected URL keyword argument `%s`.' % self.lookup_field
            )
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer()
        lookup_field = self.lookup_field

        if self.lookup_field in serializer.get_fields():
            k = serializer.get_fields()[self.lookup_field]
            if isinstance(k, serializers.HyperlinkedRelatedField):
                lookup_field = '%s__%s' % (self.lookup_field, k.lookup_field)

        lookup = self.kwargs[self.lookup_field]
        filter_kwargs = {lookup_field: lookup}

        try:
            pk = int(lookup)
        except (TypeError, ValueError):
            pass
        else:
            filter_kwargs = {'user__pk': pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    @action(methods=['POST'])
    def change_password(self, request, *args, **kwargs):
        user_profile = self.get_object()
        current_password = request.DATA.get('current_password', None)
        new_password = request.DATA.get('new_password', None)

        if new_password:
            if user_profile.user.check_password(current_password):
                user_profile.user.set_password(new_password)
                user_profile.user.save()

                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        profile = self.get_object()
        metadata = profile.metadata
        if request.DATA.get('overwrite') == 'false':
            if isinstance(request.DATA.get('metadata'), basestring):
                metadata_items = json.loads(
                    request.DATA.get('metadata')).items()
            else:
                metadata_items = request.DATA.get('metadata').items()

            for a, b in metadata_items:
                if check_if_key_exists(a, metadata):
                    metadata = replace_key_value(a, b, metadata)
                else:
                    metadata[a] = b

            profile.metadata = metadata
            profile.save()
            return Response(data=profile.metadata, status=status.HTTP_200_OK)

        return super(UserProfileViewSet, self).partial_update(request, *args,
                                                              **kwargs)
