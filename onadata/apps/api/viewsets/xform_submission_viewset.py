import re

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.authentication import (
    BasicAuthentication,
    TokenAuthentication)
from rest_framework.response import Response
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer

from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.api.permissions import IsAuthenticatedSubmission
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.authentication import EnketoTokenAuthentication
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.openrosa_headers_mixin import OpenRosaHeadersMixin
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.data_serializer import SubmissionSerializer, JSONSubmissionSerializer
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)
xml_error_re = re.compile('>(.*)<')
    

class XFormSubmissionViewSet(AuthenticateHeaderMixin,
                             OpenRosaHeadersMixin, mixins.CreateModelMixin,
                             BaseViewset,
                             viewsets.GenericViewSet):

    authentication_classes = (DigestAuthentication,
                              BasicAuthentication,
                              TokenAuthentication,
                              EnketoTokenAuthentication)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = Instance
    permission_classes = (permissions.AllowAny, IsAuthenticatedSubmission)
    renderer_classes = (TemplateXMLRenderer,
                        JSONRenderer,
                        BrowsableAPIRenderer)
    serializer_class = SubmissionSerializer
    template_name = 'submission.xml'

    def get_serializer_class(self):
        if 'application/json' in self.request.content_type.lower():
            return JSONSubmissionSerializer

        return SubmissionSerializer
    
    def handle_exception(self, exc):
        if hasattr(exc, 'response'):
            return exc.response
        return super(XFormSubmissionViewSet, self).handle_exception(exc)
        # if not error:
        #     error_msg = _(u"Unable to create submission.")
        #     status_code = status.HTTP_400_BAD_REQUEST
        # elif isinstance(error, basestring):
        #     error_msg = error
        #     status_code = status.HTTP_400_BAD_REQUEST
        # elif not is_json_request:
        #     return error
        # else:
        #     error_msg = xml_error_re.search(error.content).groups()[0]
        #     status_code = error.status_code

        # return Response({'error': error_msg},
        #                 headers=self.get_openrosa_headers(request),
        #                 status=status_code)
