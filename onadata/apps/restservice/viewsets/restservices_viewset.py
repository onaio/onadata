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
from onadata.libs.stepup import RequiresStepUp
from onadata.libs.stepup.policy import GATE_CHANGE_WEBHOOK, is_gated
from onadata.libs.utils.common_tags import TEXTIT

# pylint: disable=invalid-name
BaseViewset = get_baseviewset_class()

#: Where a service sends: which form's data, in what format, to what URL.
DESTINATION_FIELDS = ("xform", "name", "service_url")

#: A TextIt service sends to these instead, and they live in MetaData rather
#: than on the row, so they cannot be compared to a stored value here. Any
#: write to one repoints the service, so it is gated whenever present.
TEXTIT_DESTINATION_FIELDS = ("auth_token", "flow_uuid", "contacts")


def get_serializer_class(name):
    """Returns a serilizer class with the given ``name``."""
    services_to_serializers = getattr(settings, "REST_SERVICES_TO_SERIALIZERS", {})
    serializer_class = services_to_serializers.get(name)

    if serializer_class:
        return import_string(serializer_class)

    if name == TEXTIT:
        return TextItSerializer

    return RestServiceSerializer


def _changes_destination(instance, validated_data) -> bool:
    if any(
        field in validated_data and validated_data[field] != getattr(instance, field)
        for field in DESTINATION_FIELDS
    ):
        return True
    if instance.name == TEXTIT:
        return any(field in validated_data for field in TEXTIT_DESTINATION_FIELDS)
    return False


# pylint: disable=too-many-ancestors
class RestServicesViewSet(
    RequiresStepUp,
    AuthenticateHeaderMixin,
    CacheControlMixin,
    LastModifiedMixin,
    BaseViewset,
    ModelViewSet,
):
    """
    This endpoint provides access to form rest services.
    """

    queryset = RestService.objects.select_related("xform").filter(
        xform__deleted_at__isnull=True,
        xform__project__organization__is_active=True,
    )
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

    def create(self, request, *args, **kwargs):
        refusal = self._step_up_refusal(request)
        if refusal is not None:
            return refusal
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        refusal = self._step_up_refusal(
            request, self.get_object(), partial=kwargs.get("partial", False)
        )
        if refusal is not None:
            return refusal
        return super().update(request, *args, **kwargs)

    def _step_up_refusal(self, request, instance=None, partial=False):
        """Refuse a new service, or one sent somewhere else, without a grant.

        Validated first, so a request the write would reject keeps its grant.
        """
        if not is_gated(GATE_CHANGE_WEBHOOK):
            return None
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if instance is not None and not _changes_destination(
            instance, serializer.validated_data
        ):
            return None
        return self.check_step_up(request, GATE_CHANGE_WEBHOOK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer_class = get_serializer_class(instance.name)

        if serializer_class:
            serializer = serializer_class(instance)
        else:
            serializer = self.get_serializer(instance)

        return Response(serializer.data)
