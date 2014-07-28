from django.forms import widgets
from rest_framework import serializers

from onadata.apps.logger.models import XForm
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    formid = serializers.Field(source='id')
    title = serializers.CharField(max_length=255, source='title')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user', lookup_field='username')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    public_data = BooleanField(
        source='shared_data')
    require_auth = BooleanField(
        source='require_auth', widget=widgets.CheckboxInput())
    tags = TagListSerializer(read_only=True)
    users = serializers.SerializerMethodField('get_xform_permissions')
    last_submission = serializers.SerializerMethodField('get_last_submission')
    num_submissions = serializers.SerializerMethodField('get_num_submissions')

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user',
                   'has_start_time', 'shared', 'shared_data')

    def get_xform_permissions(self, obj):
        return get_object_users_with_permissions(obj)

    def get_num_submissions(self, obj):
        if obj:
            return obj.instances.count()

    def get_last_submission(self, obj):
        if obj:
            dates = obj.instances.order_by('-date_created').values_list(
                'date_created', flat=True)

            return dates and dates[0]
