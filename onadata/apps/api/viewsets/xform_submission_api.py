import pytz

from datetime import datetime

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer

from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.serializers.data_serializer import SubmissionSerializer
from onadata.libs.utils.logger_tools import safe_create_instance


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)

class TemplateXMLRenderer(TemplateHTMLRenderer):
    format = 'xml'
    media_type = 'text/xml'


class XFormSubmissionApi(viewsets.ModelViewSet):
    authentication_classes = (DigestAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = Instance
    permission_classes = (permissions.AllowAny,)
    renderer_classes = (TemplateXMLRenderer,)
    serializer_class = SubmissionSerializer
    template_name = 'submission.xml'

    def get_openrosa_headers(self, request):
        tz = pytz.timezone(settings.TIME_ZONE)
        dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')

        return {
            'Date': dt,
            'Location': request.build_absolute_uri(request.path),
            'X-OpenRosa-Version': '1.0',
            'X-OpenRosa-Accept-Content-Length': DEFAULT_CONTENT_LENGTH
        }

    def filter_queryset(self, queryset):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        if username is not None and self.request.user.is_anonymous():
            profile = get_object_or_404(
                UserProfile, user__username=username.lower())

            if profile.require_auth:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(user=profile.user)
        else:
            queryset = super(XFormSubmissionApi, self)\
                .filter_queryset(queryset)

        return queryset

    def create(self, request, *args, **kwargs):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)
        elif username is not None and self.request.user.is_anonymous():
            profile = get_object_or_404(
                UserProfile, user__username=username.lower())

            if profile.require_auth:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)

        xml_file = request.FILES.get('xml_submission_file')
        media_files = [request.FILES.get('media_file')]

        error, instance = safe_create_instance(
            username, xml_file, media_files, None, request)

        if error:
            return error

        if instance is None:
            return Response(_(u"Unable to create submission."))

        context = self.get_serializer_context()
        serializer = SubmissionSerializer(instance, context=context)

        return Response(serializer.data,
                        headers=self.get_openrosa_headers(request),
                        status=status.HTTP_201_CREATED,
                        template_name=self.template_name)
