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
    key = serializers.CharField(max_length=255, read_only=True)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=255, required=False)

    widget_type = serializers.ChoiceField(choices=Widget.WIDGETS_TYPES)
    view_type = serializers.CharField(max_length=50)
    column = serializers.CharField(max_length=50)
    group_by = serializers.CharField(max_length=50, required=False)

    content_object = GenericRelatedField({
        XForm: serializers.HyperlinkedRelatedField(view_name='xform-detail',
                                                   lookup_field='pk'),
        DataView: serializers.HyperlinkedRelatedField(
            view_name='dataviews-detail', lookup_field='pk'),
    })

    data = serializers.SerializerMethodField()

    class Meta:
        model = Widget
        fields = ('url', 'key', 'title', 'description', 'widget_type',
                  'view_type', 'column', 'group_by', 'content_object', 'data')

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
            if 'content_object' in attrs:
                content_object = attrs.get('content_object')

                if isinstance(content_object, XForm):
                    xform = content_object
                elif isinstance(content_object, DataView):
                    # must be a dataview
                    xform = content_object.xform

            data_dictionary = xform.data_dictionary()

            if column not in data_dictionary.get_headers():
                raise serializers.ValidationError(_(
                    u"'{}' not in the form".format(column)
                ))

        return attrs

    def validate_content_object(self, value):

        request = self.context.get('request')
        users = get_users_with_perms(
            value.project, attach_perms=False, with_group_users=False
        )

        if request.user not in users:
            raise serializers.ValidationError(_(
                u"You don't have permission to the XForm"
            ))

        return value
