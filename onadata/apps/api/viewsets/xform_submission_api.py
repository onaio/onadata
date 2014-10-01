import StringIO
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.authentication import BasicAuthentication
from rest_framework.response import Response
from rest_framework.renderers import BrowsableAPIRenderer

from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.mixins.openrosa_headers_mixin import OpenRosaHeadersMixin
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.data_serializer import SubmissionSerializer
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


def is_json(request):
    return 'application/json' in request.content_type.lower()


def dict_lists2strings(d):
    """Convert lists in a dict to joined strings.

    :param d: The dict to convert.
    :returns: The converted dict."""
    for k, v in d.items():
        if isinstance(v, list):
            d[k] = ' '.join(v)
        elif isinstance(v, dict):
            d[k] = dict_lists2strings(v)

    return d


def json_request2xform(request):
    dict_form = request.DATA

    # convert lists in submission dict to joined strings
    submission = dict_lists2strings(dict_form['submission'])

    xml_string = dict2xform(submission,
                            dict_form['id'])

    return StringIO.StringIO(xml_string)


class XFormSubmissionApi(OpenRosaHeadersMixin,
                         mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
Implements OpenRosa Api [FormSubmissionAPI](\
    https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI)

## Submit an XML XForm submission

<pre class="prettyprint">
<b>POST</b> /api/v1/submissions</pre>
> Example
>
>       curl -X POST -F xml_submission_file=@/path/to/submission.xml \
https://ona.io/api/v1/submissions

    """
    authentication_classes = (DigestAuthentication, BasicAuthentication)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    queryset = Instance.objects.all()
    permission_classes = (permissions.AllowAny,)
    renderer_classes = (TemplateXMLRenderer, BrowsableAPIRenderer)
    serializer_class = SubmissionSerializer
    template_name = 'submission.xml'

    def create(self, request, *args, **kwargs):
        username = self.kwargs.get('username')

        if self.request.user.is_anonymous():
            if username is None:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                user = get_object_or_404(User, username=username.lower())

                profile, created = UserProfile.objects.get_or_create(user=user)

                if profile.require_auth:
                    # raises a permission denied exception,
                    # forces authentication
                    self.permission_denied(self.request)
        elif not username:
            # get the username from the user if not set
            username = (request.user and request.user.username)

        if request.method.upper() == 'HEAD':
            return Response(status=status.HTTP_204_NO_CONTENT,
                            headers=self.get_openrosa_headers(request),
                            template_name=self.template_name)

        if is_json(request):
            xml_file = json_request2xform(request)
            media_files = []
        else:
            # assume XML submission
            xml_file_list = request.FILES.pop('xml_submission_file', [])
            xml_file = xml_file_list[0] if len(xml_file_list) else None
            media_files = request.FILES.values()

        error, instance = safe_create_instance(
            username, xml_file, media_files, None, request)

        if error or not instance:
            if not error:
                error = _(u"Unable to create submission.")
            elif not is_json(request):
                return error
            else:
                error = error.content

            return HttpResponseBadRequest(error,
                                          mimetype='application/json',
                                          status=400)

        context = self.get_serializer_context()
        serializer = SubmissionSerializer(instance, context=context)

        return Response(serializer.data,
                        headers=self.get_openrosa_headers(request),
                        status=status.HTTP_201_CREATED,
                        template_name=self.template_name)
