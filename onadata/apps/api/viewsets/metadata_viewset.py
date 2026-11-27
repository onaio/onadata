# -*- coding: utf-8 -*-
"""
The /api/v1/metadata API implementation.

List, Create, Update, Delete MetaData objects.
"""
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.logger.models import XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import (
    MediaFileContentNegotiation,
    MediaFileRenderer,
)
from onadata.apps.api.tools import get_baseviewset_class
from onadata.libs.data import strtobool
from onadata.libs.stepup import RequiresStepUp
from onadata.libs.stepup.owners import content_owners
from onadata.libs.stepup.policy import (
    ADMIN_ROLE_NAMES,
    GATE_CHANGE_WEBHOOK,
    GATE_PUBLISH_DATA,
    GATE_SHARE_FORM_ADMIN,
)
from onadata.libs.stepup.sharing import appoints_admins
from onadata.libs.utils.common_tags import TEXTIT, XFORM_META_PERMS


BaseViewset = get_baseviewset_class()

PUBLIC_LINK = "public_link"


def _meta_perms_slots(value):
    return dict(enumerate(value.split("|"))) if value else {}


def _introduces_admin_meta_perms(content_object, data_value):
    """Whether ``data_value`` appoints owners or managers of the form.

    Meta permissions give a form's editors, data-entry and read-only users the
    role in their slot. A slot newly set to owner or manager appoints admins,
    and so does a value that promotes a current user once applied."""
    current = MetaData.xform_meta_permission(content_object)
    old = _meta_perms_slots(current.data_value if current else "")
    names_new_admin = any(
        role in ADMIN_ROLE_NAMES and old.get(slot) != role
        for slot, role in _meta_perms_slots(data_value).items()
    )
    return names_new_admin or (
        isinstance(content_object, XForm)
        and appoints_admins(content_object, data_value)
    )


def _is_true(value):
    """Any spelling of true, not only the ``"True"`` a public link is stored
    as, so a value a reader might accept later is gated now."""
    try:
        return bool(strtobool(str(value)))
    except ValueError:
        return False


def _turns_on_public_link(content_object, data_value):
    return _is_true(data_value) and not MetaData.public_link(content_object)


def _changes_textit(content_object, data_value):
    """The TextIt settings carry the token and contacts a form's TextIt
    service posts submissions with."""
    return MetaData.textit(content_object) != data_value


# pylint: disable=too-many-ancestors
class MetaDataViewSet(
    AuthenticateHeaderMixin,
    CacheControlMixin,
    ETagsMixin,
    RequiresStepUp,
    BaseViewset,
    viewsets.ModelViewSet,
):
    """
    List, Create, Update, Delete MetaData objects.
    """

    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = MetaData.objects.filter(deleted_at__isnull=True).select_related()
    permission_classes = (MetaDataObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer,
    )
    serializer_class = MetaDataSerializer

    def _change_refusal(self, request, content_object, data_type, data_value):
        """Refuse the gated change writing ``data_value`` as ``data_type`` on
        ``content_object`` would make, or None."""
        return self.gated_change_refusal(
            request,
            (
                (
                    GATE_SHARE_FORM_ADMIN,
                    lambda: data_type == XFORM_META_PERMS
                    and _introduces_admin_meta_perms(content_object, data_value),
                ),
                (
                    GATE_PUBLISH_DATA,
                    data_type == PUBLIC_LINK
                    and _turns_on_public_link(content_object, data_value),
                ),
                (
                    GATE_CHANGE_WEBHOOK,
                    data_type == TEXTIT and _changes_textit(content_object, data_value),
                ),
            ),
            owners=content_owners(content_object),
        )

    def create(self, request, *args, **kwargs):
        return self.gated_create(
            request,
            lambda data: self._change_refusal(
                request,
                self.get_serializer().get_content_object(data),
                data.get("data_type"),
                data.get("data_value"),
            ),
        )

    def update(self, request, *args, **kwargs):
        """An update can change the type as well as the value, so the gates
        read what the row will hold afterwards."""

        def refusal_for(instance, validated_data):
            return self._change_refusal(
                request,
                instance.content_object,
                validated_data.get("data_type", instance.data_type),
                validated_data.get("data_value", instance.data_value),
            )

        return self.gated_update(
            request, refusal_for, partial=kwargs.pop("partial", False)
        )

    def retrieve(self, request, *args, **kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.object = self.get_object()
        if (
            isinstance(request.accepted_renderer, MediaFileRenderer)
            and self.object.data_file is not None
        ):

            return get_media_file_response(self.object, request)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)
