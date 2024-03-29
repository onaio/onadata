# -*- coding: utf-8 -*-
"""
Implements the /api/v1/restservices endpoint.
"""
from django.conf import settings
from django.utils.module_loading import import_string

from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import RestServiceObjectPermissions
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.serializers.restservices_serializer import RestServiceSerializer
from onadata.libs.serializers.textit_serializer import TextItSerializer
from onadata.libs.utils.common_tags import TEXTIT

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()


def get_serializer_class(name):
    """Returns a serilizer class with the given ``name``."""
    services_to_serializers = getattr(settings, "REST_SERVICES_TO_SERIALIZERS", {})
    serializer_class = services_to_serializers.get(name)

    if serializer_class:
        return import_string(serializer_class)

    if name == TEXTIT:
        return TextItSerializer

    return RestServiceSerializer


# pylint: disable=too-many-ancestors
class RestServicesViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    LastModifiedMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    This endpoint provides access to form rest services.
    """

    queryset = RestService.objects.select_related("xform")
    serializer_class = RestServiceSerializer
    permission_classes = [
        RestServiceObjectPermissions,
    ]
    filter_backends = (filters.RestServiceFilter,)

    def get_serializer_class(self):
        name = self.request.data.get("name")
        serializer_class = get_serializer_class(name)

        if serializer_class:
            return serializer_class

        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer_class = get_serializer_class(instance.name)

        if serializer_class:
            serializer = serializer_class(instance)
        else:
            serializer = self.get_serializer(instance)

        return Response(serializer.data)
