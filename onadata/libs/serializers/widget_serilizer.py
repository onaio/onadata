from django.core.validators import ValidationError
from django.utils.translation import ugettext as _

from rest_framework import serializers
from generic_relations.relations import GenericRelatedField
from guardian.shortcuts import get_users_with_perms

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.widget import Widget
from onadata.libs.utils.string import str2bool


class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='widgets-detail')
    key = serializers.CharField(max_length=255, source='key', read_only=True)
    title = serializers.CharField(max_length=255, source='title',
                                  required=False)
    description = serializers.CharField(max_length=255, source='description',
                                        required=False)

    widget_type = serializers.ChoiceField(choices=Widget.WIDGETS_TYPES,
                                          source='widget_type')
    view_type = serializers.CharField(max_length=50, source='view_type')
    column = serializers.CharField(max_length=50, source='column')
    group_by = serializers.CharField(max_length=50, source='group_by',
                                     required=False)

    content_object = GenericRelatedField({
        XForm: serializers.HyperlinkedRelatedField(view_name='xform-detail',
                                                   lookup_field='pk'),
        DataView: serializers.HyperlinkedRelatedField(
            view_name='dataviews-detail', lookup_field='pk'),
    })

    data = serializers.SerializerMethodField(
        'get_widget_data')

    class Meta:
        model = Widget
        fields = ('url', 'key', 'title', 'description', 'widget_type',
                  'view_type', 'column', 'group_by', 'content_object', 'data')

    def get_widget_data(self, obj):
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

    def validate_column(self, attrs, source):
        column = attrs.get('column')

        # Get the form
        if 'content_object' in attrs or self.object:

            if 'content_object' in attrs:
                content_object = attrs.get('content_object')
            else:
                content_object = self.object.content_object

            if isinstance(content_object, XForm):
                xform = content_object
            elif isinstance(content_object, DataView):
                # must be a dataview
                xform = content_object.xform

            data_dictionary = xform.data_dictionary()

            if column not in data_dictionary.get_headers():
                raise ValidationError(_("'{}' not in the form".format(column)))

        return attrs

    def validate_content_object(self, attrs, source):

        if 'content_object' in attrs:
            content_object = attrs.get('content_object')
            request = self.context.get('request')
            users = get_users_with_perms(content_object.project,
                                         attach_perms=False,
                                         with_group_users=False)

            if request.user not in users:
                raise ValidationError("You don't have perms")

        return attrs
