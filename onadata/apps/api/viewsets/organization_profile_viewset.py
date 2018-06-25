import json
from django.conf import settings

from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.apps.api.models.organization_profile import OrganizationProfile

from onadata.apps.api import permissions
from onadata.apps.api.tools import get_baseviewset_class, load_class
from onadata.libs.utils.common_tools import merge_dicts
from onadata.libs.filters import (OrganizationPermissionFilter,
                                  OrganizationsSharedWithUserFilter)
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.organization_member_serializer import \
    OrganizationMemberSerializer
from onadata.libs.serializers.organization_serializer import (
    OrganizationSerializer)


BaseViewset = get_baseviewset_class()


def serializer_from_settings():
    if settings.ORG_PROFILE_SERIALIZER:
        return load_class(settings.ORG_PROFILE_SERIALIZER)

    return OrganizationSerializer


class OrganizationProfileViewSet(AuthenticateHeaderMixin,
                                 CacheControlMixin,
                                 ETagsMixin,
                                 ObjectLookupMixin,
                                 BaseViewset,
                                 ModelViewSet):
    """
    List, Retrieve, Update, Create/Register Organizations.
    """
    queryset = OrganizationProfile.objects.filter(user__is_active=True)
    serializer_class = serializer_from_settings()
    lookup_field = 'user'
    permission_classes = [permissions.OrganizationProfilePermissions]
    filter_backends = (OrganizationPermissionFilter,
                       OrganizationsSharedWithUserFilter)

    @action(methods=['DELETE', 'GET', 'POST', 'PUT'], detail=True)
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        data = merge_dicts(request.data,
                           request.query_params.dict(),
                           {'organization': organization.pk})

        if request.method == 'POST' and 'username' not in data:
            data['username'] = None

        if request.method == 'DELETE':
            data['remove'] = True

        if request.method == 'PUT' and 'role' not in data:
            data['role'] = None

        serializer = OrganizationMemberSerializer(data=data)

        if serializer.is_valid():
            serializer.save()

        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        self.etag_data = json.dumps(data)
        resp_status = status.HTTP_201_CREATED if request.method == 'POST' \
            else status.HTTP_200_OK

        return Response(status=resp_status, data=serializer.data())
