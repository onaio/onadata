from rest_framework import serializers
from onadata.apps.logger.models.attachment import Attachment
from onadata.libs.utils.image_tools import image_url


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='attachment-detail',
                                               lookup_field='pk')
    download_url = serializers.SerializerMethodField('get_download_url')
    small_download_url = serializers.SerializerMethodField(
        'get_small_download_url')
    medium_download_url = serializers.SerializerMethodField(
        'get_medium_download_url')
    xform = serializers.Field(source='instance.xform.pk')
    instance = serializers.Field(source='instance.pk')
    filename = serializers.Field(source='media_file.name')

    class Meta:
        fields = ('url', 'filename', 'mimetype', 'id', 'xform', 'instance',
                  'download_url', 'small_download_url', 'medium_download_url')
        lookup_field = 'pk'
        model = Attachment

    def get_download_url(self, obj):
        if obj is not None:
            return obj.media_file.url if obj.media_file.url else None

    def get_small_download_url(self, obj):
        if obj.mimetype.startswith('image'):
            return image_url(obj, 'small')

    def get_medium_download_url(self, obj):
        if obj.mimetype.startswith('image'):
            return image_url(obj, 'medium')
