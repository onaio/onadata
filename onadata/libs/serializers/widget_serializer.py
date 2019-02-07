from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import resolve, get_script_prefix, Resolver404
from django.http import Http404
from django.utils.translation import ugettext as _
from future.moves.urllib.parse import urlparse
from guardian.shortcuts import get_users_with_perms
from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.models.xform import XForm
from onadata.libs.permissions import OwnerRole, is_organization
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.utils.chart_tools import get_field_from_field_xpath
from onadata.libs.utils.string import str2bool


class GenericRelatedField(serializers.HyperlinkedRelatedField):
    default_error_messages = {
        'incorrect_match': _('`{input}` is not a valid relation.')
    }

    def __init__(self, *args, **kwargs):
        self.view_names = ['xform-detail', 'dataviews-detail']
        self.resolve = resolve
        self.reverse = reverse
        self.format = kwargs.pop('format', 'json')
        super(serializers.RelatedField, self).__init__(*args, **kwargs)

    def _setup_field(self, view_name):
        self.lookup_url_kwarg = self.lookup_field

        if view_name == 'xform-detail':
            self.queryset = XForm.objects.all()

        if view_name == 'dataviews-detail':
            self.queryset = DataView.objects.all()

    def to_representation(self, value):
        if isinstance(value, XForm):
            self.view_name = 'xform-detail'
        elif isinstance(value, DataView):
            self.view_name = 'dataviews-detail'
        else:
            raise Exception(_(u"Unknown type for content_object."))

        self._setup_field(self.view_name)

        return super(GenericRelatedField, self).to_representation(value)

    def to_internal_value(self, data):
        try:
            http_prefix = data.startswith(('http:', 'https:'))
        except AttributeError:
            self.fail('incorrect_type', data_type=type(data).__name__)
        input_data = data
        if http_prefix:
            # If needed convert absolute URLs to relative path
            data = urlparse(data).path
            prefix = get_script_prefix()
            if data.startswith(prefix):
                data = '/' + data[len(prefix):]

        try:
            match = self.resolve(data)
        except Resolver404:
            self.fail('no_match')

        if match.view_name not in self.view_names:
            self.fail('incorrect_match', input=input_data)

        self._setup_field(match.view_name)

        try:
            return self.get_object(match.view_name, match.args, match.kwargs)
        except (ObjectDoesNotExist, TypeError, ValueError):
            self.fail('does_not_exist')

        return data


class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField()
    url = serializers.HyperlinkedIdentityField(
        view_name='widgets-detail',
        lookup_field='pk'
    )
    content_object = GenericRelatedField()
    key = serializers.CharField(read_only=True)
    data = serializers.SerializerMethodField()
    order = serializers.IntegerField(required=False)
    metadata = JsonField(required=False)

    class Meta:
        model = Widget
        fields = ('id', 'url', 'key', 'title', 'description', 'widget_type',
                  'order', 'view_type', 'column', 'group_by', 'content_object',
                  'data', 'aggregation', 'metadata')

    def get_data(self, obj):
        # Get the request obj
        request = self.context.get('request')

        # Check if data flag is present
        data_flag = request.GET.get('data')
        key = request.GET.get('key')

        if (str2bool(data_flag) or key) and obj:
            data = Widget.query_data(obj)
        else:
            data = []

        return data

    def validate(self, attrs):
        column = attrs.get('column')

        # Get the form
        if 'content_object' in attrs:
            content_object = attrs.get('content_object')

            if isinstance(content_object, XForm):
                xform = content_object
            elif isinstance(content_object, DataView):
                # must be a dataview
                xform = content_object.xform

            try:
                # Check if column exists in xform
                get_field_from_field_xpath(column, xform)
            except Http404:
                raise serializers.ValidationError({
                    'column': (u"'{}' not in the form.".format(column))
                })

        order = attrs.get('order')

        # Set the order
        if order:
            self.instance.to(order)

        return attrs

    def validate_content_object(self, value):
        request = self.context.get('request')
        users = get_users_with_perms(
            value.project, attach_perms=False, with_group_users=False
        )

        profile = value.project.organization.profile
        # Shared or an admin in the organization
        if request.user not in users and not\
            is_organization(profile) and not\
            OwnerRole.user_has_role(request.user,
                                    profile):
            raise serializers.ValidationError(_(
                u"You don't have permission to the Project."
            ))

        return value
