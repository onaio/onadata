from django.forms import widgets
from rest_framework import serializers

from onadata.apps.logger.models import XForm
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer


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
    metadata = serializers.SerializerMethodField('get_xform_metadata')

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user',
                   'has_start_time', 'shared', 'shared_data')

    def get_xform_permissions(self, obj):
        return get_object_users_with_permissions(obj)

    def get_xform_metadata(self, obj):
        return MetaDataSerializer(obj.metadata_set.all(), many=True).data
