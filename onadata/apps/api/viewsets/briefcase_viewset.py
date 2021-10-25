from xml.dom import NotFoundErr
from django.conf import settings
from django.core.files import File
from django.core.validators import ValidationError
from django.contrib.auth.models import User
from django.http import Http404
from django.utils.translation import ugettext as _
from django.utils import six

from rest_framework import exceptions
from rest_framework import mixins
from rest_framework import status
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response

from onadata.apps.api.tools import get_media_file_response
from onadata.apps.api.permissions import ViewDjangoObjectPermissions
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.mixins.openrosa_headers_mixin import get_openrosa_headers
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.xform_serializer import XFormListSerializer
from onadata.libs.serializers.xform_serializer import XFormManifestSerializer
from onadata.libs.utils.logger_tools import publish_form
from onadata.libs.utils.logger_tools import PublishXForm
from onadata.libs.utils.viewer_tools import get_form


def _extract_uuid(text):
    if isinstance(text, six.string_types):
        form_id_parts = text.split('/')

        if form_id_parts.__len__() < 2:
            raise ValidationError(_(u"Invalid formId %s." % text))

        text = form_id_parts[1]
        text = text[text.find("@key="):-1].replace("@key=", "")

        if text.startswith("uuid:"):
            text = text.replace("uuid:", "")

    return text


def _extract_id_string(formId):
    if isinstance(formId, six.string_types):
        return formId[0:formId.find('[')]

    return formId


def _parse_int(num):
    try:
        return num and int(num)
    except ValueError:
        pass


class BriefcaseViewset(mixins.CreateModelMixin,
                       mixins.RetrieveModelMixin, mixins.ListModelMixin,
                       viewsets.GenericViewSet):
    """
    Implements the [Briefcase Aggregate API](\
    https://code.google.com/p/opendatakit/wiki/BriefcaseAggregateAPI).
    """
    authentication_classes = (DigestAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    queryset = XForm.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          ViewDjangoObjectPermissions)
    renderer_classes = (TemplateXMLRenderer, BrowsableAPIRenderer)
    serializer_class = XFormListSerializer
    template_name = 'openrosa_response.xml'

    def get_object(self, queryset=None):
        formId = self.request.GET.get('formId', '')
        id_string = _extract_id_string(formId)
        uuid = _extract_uuid(formId)
        username = self.kwargs.get('username')

        obj = get_object_or_404(Instance,
                                xform__user__username__iexact=username,
                                xform__id_string__iexact=id_string,
                                uuid=uuid)
        self.check_object_permissions(self.request, obj.xform)

        return obj

    def filter_queryset(self, queryset):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous:
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)

        if username is not None and self.request.user.is_anonymous:
            profile = get_object_or_404(
                UserProfile, user__username__iexact=username)

            if profile.require_auth:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                queryset = queryset.filter(user=profile.user)
        else:
            queryset = super(BriefcaseViewset, self).filter_queryset(queryset)

        formId = self.request.GET.get('formId', '')

        if formId.find('[') != -1:
            formId = _extract_id_string(formId)

        xform_kwargs = {
            'queryset': queryset,
            'id_string__iexact': formId
        }
        if username:
            xform_kwargs['user__username__iexact'] = username
        xform = get_form(xform_kwargs)
        self.check_object_permissions(self.request, xform)
        instances = Instance.objects.filter(
            xform=xform, deleted_at__isnull=True).values(
                'pk', 'uuid')
        if xform.encrypted:
            instances = instances.filter(media_all_received=True)
        instances = instances.order_by('pk')
        num_entries = self.request.GET.get('numEntries')
        cursor = self.request.GET.get('cursor')

        cursor = _parse_int(cursor)
        if cursor:
            instances = instances.filter(pk__gt=cursor)

        num_entries = _parse_int(num_entries)
        if num_entries:
            instances = instances[:num_entries]

        # Using len() instead of .count() to prevent an extra
        # database call; len() will load the instances in memory allowing
        # us to pre-load the queryset before generating the response
        # and removes the need to perform a count on the database.
        instance_count = len(instances)

        if instance_count > 0:
            last_instance = instances[instance_count - 1]
            self.resumptionCursor = last_instance.get('pk')
        elif instance_count == 0 and cursor:
            self.resumptionCursor = cursor
        else:
            self.resumptionCursor = 0

        return instances

    def create(self, request, *args, **kwargs):
        if request.method.upper() == 'HEAD':
            return Response(status=status.HTTP_204_NO_CONTENT,
                            headers=get_openrosa_headers(request),
                            template_name=self.template_name)

        xform_def = request.FILES.get('form_def_file', None)
        response_status = status.HTTP_201_CREATED
        username = kwargs.get('username')
        form_user = (username and get_object_or_404(User, username=username)) \
            or request.user

        if not request.user.has_perm('can_add_xform', form_user.profile):
            raise exceptions.PermissionDenied(
                detail=_(u"User %(user)s has no permission to add xforms to "
                         "account %(account)s" %
                         {'user': request.user.username,
                          'account': form_user.username}))
        data = {}

        if isinstance(xform_def, File):
            do_form_upload = PublishXForm(xform_def, form_user)
            dd = publish_form(do_form_upload.publish_xform)

            if isinstance(dd, XForm):
                data['message'] = _(
                    u"%s successfully published." % dd.id_string)
            else:
                data['message'] = dd['text']
                response_status = status.HTTP_400_BAD_REQUEST
        else:
            data['message'] = _(u"Missing xml file.")
            response_status = status.HTTP_400_BAD_REQUEST

        return Response(data, status=response_status,
                        headers=get_openrosa_headers(request,
                                                     location=False),
                        template_name=self.template_name)

    def list(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset())

        data = {'instances': self.object_list,
                'resumptionCursor': self.resumptionCursor}

        return Response(data,
                        headers=get_openrosa_headers(request,
                                                     location=False),
                        template_name='submissionList.xml')

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        xml_obj = clean_and_parse_xml(self.object.xml)
        submission_xml_root_node = xml_obj.documentElement
        submission_xml_root_node.setAttribute(
            'instanceID', u'uuid:%s' % self.object.uuid)
        submission_xml_root_node.setAttribute(
            'submissionDate', self.object.date_created.isoformat()
        )

        if getattr(settings, "SUPPORT_BRIEFCASE_SUBMISSION_DATE", True):
            # Remove namespace attribute if any
            try:
                submission_xml_root_node.removeAttribute('xmlns')
            except NotFoundErr:
                pass

        data = {
            'submission_data': submission_xml_root_node.toxml(),
            'media_files': Attachment.objects.filter(instance=self.object),
            'host': request.build_absolute_uri().replace(
                request.get_full_path(), '')
        }

        return Response(
            data,
            headers=get_openrosa_headers(request, location=False),
            template_name='downloadSubmission.xml'
        )

    @action(methods=['GET'], detail=True)
    def manifest(self, request, *args, **kwargs):
        self.object = self.get_object()
        object_list = MetaData.objects.filter(data_type='media',
                                              object_id=self.object.id)
        context = self.get_serializer_context()
        serializer = XFormManifestSerializer(object_list, many=True,
                                             context=context)

        return Response(serializer.data,
                        headers=get_openrosa_headers(request, location=False))

    @action(methods=['GET'], detail=True)
    def media(self, request, *args, **kwargs):
        self.object = self.get_object()
        pk = kwargs.get('metadata')

        if not pk:
            raise Http404()

        meta_obj = get_object_or_404(
            MetaData, data_type='media', xform=self.object, pk=pk)

        return get_media_file_response(meta_obj)
