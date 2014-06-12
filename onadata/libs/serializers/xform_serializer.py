from django.forms import widgets
from rest_framework import serializers

from onadata.libs.serializers.fields.hyperlinked_multi_identity_field import\
    HyperlinkedMultiIdentityField
from onadata.apps.logger.models import XForm
from onadata.libs.serializers.tag_list_serializer import TagListSerializer


class BooleanField(serializers.BooleanField):
    def from_native(self, value):
        if value in ('true', 't', 'True', '1'):
            return True

        if value in ('false', 'f', 'False', '0'):
            return False

        return value


class XFormSerializer(serializers.HyperlinkedModelSerializer):
    url = HyperlinkedMultiIdentityField(
        view_name='xform-detail',
        lookup_fields=(('pk', 'pk'), ('owner', 'user')))
    formid = serializers.Field(source='id')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='user', lookup_field='username')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    public_data = BooleanField(
        source='shared_data')
    tags = TagListSerializer(read_only=True)

    class Meta:
        model = XForm
        read_only_fields = (
            'json', 'xml', 'date_created', 'date_modified', 'encrypted',
            'bamboo_dataset', 'last_submission_time')
        exclude = ('id', 'json', 'xml', 'xls', 'user',
                   'has_start_time', 'shared', 'shared_data')
