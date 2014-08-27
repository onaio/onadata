from django.forms import widgets
from rest_framework import serializers
from rest_framework.reverse import reverse

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
        if obj:
            return MetaDataSerializer(obj.metadata_set.all(), many=True).data

        return []


class XFormListSerializer(serializers.Serializer):
    formID = serializers.Field(source='id_string')
    name = serializers.Field(source='title')
    majorMinorVersion = serializers.SerializerMethodField('get_version')
    version = serializers.SerializerMethodField('get_version')
    hash = serializers.SerializerMethodField('get_hash')
    descriptionText = serializers.Field(source='description')
    downloadUrl = serializers.SerializerMethodField('get_url')
    manifestUrl = serializers.SerializerMethodField('get_manifest_url')

    def get_version(self, obj):
        return None

    def get_hash(self, obj):
        if obj:
            return u"md5:%s" % obj.hash

    def get_url(self, obj):
        if obj:
            kwargs = {'pk': obj.pk}
            request = self.context.get('request')

            return reverse('formlist-detail', kwargs=kwargs,
                           request=request, format='xml')

    def get_manifest_url(self, obj):
        if obj:
            kwargs = {
                'username': obj.user.username, 'id_string': obj.id_string}
            request = self.context.get('request')

            return reverse('manifest-url', kwargs=kwargs,
                           request=request)


class XFormManifestSerializer(serializers.Serializer):
    filename = serializers.Field(source='data_value')
    hash = serializers.Field('file_hash')
    downloadUrl = serializers.SerializerMethodField('get_url')

    def get_url(self, obj):
        if obj:
            kwargs = {'pk': obj.pk}
            request = self.context.get('request')
            format = obj.data_value[obj.data_value.rindex('.') + 1:]

            return reverse('metadata-detail', kwargs=kwargs,
                           request=request, format=format)
