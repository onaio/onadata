# -*- coding: utf-8 -*-
"""
XFormSubmissionViewSet module
"""

from xml.parsers.expat import ExpatError

from django.conf import settings
from django.http import UnreadablePostError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response

from onadata.apps.api.permissions import IsAuthenticatedSubmission
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.logger.models import Instance
from onadata.apps.logger.xform_instance_parser import get_deprecated_uuid_from_xml
from onadata.libs import filters
from onadata.libs.authentication import (
    DigestAuthentication,
    EnketoTokenAuthentication,
    LockoutBasicAuthentication,
)
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.openrosa_headers_mixin import OpenRosaHeadersMixin
from onadata.libs.renderers.renderers import FLOIPRenderer, TemplateXMLRenderer
from onadata.libs.serializers.data_serializer import (
    FLOIPSubmissionSerializer,
    JSONSubmissionSerializer,
    RapidProJSONSubmissionSerializer,
    RapidProSubmissionSerializer,
    SubmissionSerializer,
)
from onadata.libs.utils.logger_tools import (
    OpenRosaNotAuthenticated,
    OpenRosaResponseBadRequest,
)

BaseViewset = get_baseviewset_class()  # pylint: disable=invalid-name

# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, "DEFAULT_CONTENT_LENGTH", 10000000)
FLOIP_RESULTS_CONTENT_TYPE = "application/vnd.org.flowinterop.results+json"


class FLOIPParser(JSONParser):  # pylint: disable=too-few-public-methods
    """
    Flow Results JSON parser.
    """

    media_type = FLOIP_RESULTS_CONTENT_TYPE
    renderer_classes = FLOIPRenderer


# pylint: disable=too-many-ancestors
class XFormSubmissionViewSet(
    AuthenticateHeaderMixin,  # pylint: disable=too-many-ancestors
    OpenRosaHeadersMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    BaseViewset,
    viewsets.GenericViewSet,
):
    """
    XFormSubmissionViewSet class
    """

    authentication_classes = (
        DigestAuthentication,
        LockoutBasicAuthentication,
        TokenAuthentication,
        EnketoTokenAuthentication,
    )
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = Instance
    permission_classes = (permissions.AllowAny, IsAuthenticatedSubmission)
    renderer_classes = (
        TemplateXMLRenderer,
        JSONRenderer,
        BrowsableAPIRenderer,
        FLOIPRenderer,
    )
    serializer_class = SubmissionSerializer
    template_name = "submission.xml"
    parser_classes = (FLOIPParser, JSONParser, FormParser, MultiPartParser)
    throttle_scope = "submission"

    def get_serializer(self, *args, **kwargs):
        """
        Pass many=True flag if data is a list.
        """
        data = kwargs.get("data")
        content_type = self.request.content_type.lower()

        if isinstance(data, list) and FLOIP_RESULTS_CONTENT_TYPE in content_type:
            kwargs["many"] = True

        return super().get_serializer(*args, **kwargs)

    def get_serializer_class(self):
        """
        Returns the serializer class to be used based on content_type.
        """
        content_type = self.request.content_type.lower()

        if "application/json" in content_type:
            if "RapidProMailroom" in self.request.headers.get("User-Agent", ""):
                return RapidProJSONSubmissionSerializer

            self.request.accepted_renderer = JSONRenderer()
            self.request.accepted_media_type = "application/json"
            return JSONSubmissionSerializer

        if "application/x-www-form-urlencoded" in content_type:
            return RapidProSubmissionSerializer

        if FLOIP_RESULTS_CONTENT_TYPE in content_type:
            self.request.accepted_renderer = FLOIPRenderer()
            self.request.accepted_media_type = FLOIP_RESULTS_CONTENT_TYPE
            return FLOIPSubmissionSerializer

        return SubmissionSerializer

    def create(self, request, *args, **kwargs):
        if request.method.upper() == "HEAD":
            return Response(
                status=status.HTTP_204_NO_CONTENT, template_name=self.template_name
            )

        instance = self._get_deprecated_instance(request, kwargs.get("xform_pk"))

        if instance is not None:
            return self._edit(instance)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Handle submission edit requests.

        Uses the SubmissionSerializer to handle decryption of encrypted
        submissions and save the edit via safe_create_instance.
        """
        if request.method.upper() == "HEAD":
            return Response(
                status=status.HTTP_204_NO_CONTENT, template_name=self.template_name
            )

        instance = get_object_or_404(
            self._get_editable_instances(kwargs.get("xform_pk")), pk=kwargs.get("pk")
        )

        return self._edit(instance)

    def _get_editable_instances(self, xform_pk):
        return Instance.objects.filter(
            xform_id=xform_pk,
            xform__deleted_at__isnull=True,
            xform__project__organization__is_active=True,
        )

    def _get_deprecated_instance(self, request, xform_pk):
        """Return the submission replaced by an edit whose XML does not name it.

        The deprecatedID of an encrypted edit is inside the encrypted file, so
        the X-OpenRosa-Deprecated-Id header Enketo sends is used instead.
        """
        deprecated_id = request.headers.get("X-OpenRosa-Deprecated-Id")
        xml_file = request.FILES.get("xml_submission_file")

        if not (xform_pk and deprecated_id and xml_file):
            return None

        xml = xml_file.read()
        xml_file.seek(0)

        try:
            if get_deprecated_uuid_from_xml(xml):
                return None
        except (ExpatError, ValueError):
            return None

        return (
            self._get_editable_instances(xform_pk)
            .filter(uuid=deprecated_id.removeprefix("uuid:"))
            .first()
        )

    def _edit(self, instance):
        serializer = self.get_serializer(instance, data=self.request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def handle_exception(self, exc):
        """
        Handles exceptions thrown by handler method and
        returns appropriate error response.
        """
        if hasattr(exc, "response"):
            return exc.response

        if isinstance(exc, UnreadablePostError):
            return OpenRosaResponseBadRequest(
                _("Unable to read submitted file, please try re-submitting.")
            )

        try:
            if exc.status_code == 401:
                auth_header = self.get_authenticate_header(self.request)
                response = OpenRosaNotAuthenticated(
                    data=exc.detail,
                    headers={"WWW-Authenticate": auth_header},
                )
                response.exception = True
                return response
        except AttributeError:
            # 'Http404' object has no attribute 'status_code'
            pass

        return super().handle_exception(exc)
