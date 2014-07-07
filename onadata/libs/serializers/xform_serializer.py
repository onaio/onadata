from django.forms import widgets
from rest_framework import serializers

from onadata.apps.logger.models import XForm
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    formid = serializers.Field(source='id')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user', lookup_field='username')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    public_data = BooleanField(
        source='shared_data')
    tags = TagListSerializer(read_only=True)
    users = serializers.Field(source='get_xform_permissions')

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user',
                   'has_start_time', 'shared', 'shared_data')
