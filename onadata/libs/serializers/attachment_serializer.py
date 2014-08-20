from rest_framework import serializers
from rest_framework.reverse import reverse
from onadata.apps.logger.models.attachment import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='attachment-detail',
                                               lookup_field='pk')
    download_url = serializers.SerializerMethodField('get_download_url')
    xform = serializers.Field(source='instance.xform.pk')
    data_id = serializers.Field(source='instance.pk')
    filename = serializers.Field(source='media_file.name')

    class Meta:
        fields = ('url', 'download_url', 'id', 'xform', 'data_id',
                  'mimetype', 'filename')
        lookup_field = 'pk'
        model = Attachment

    def get_download_url(self, obj):
        if obj is not None:
            kwargs = {'pk': obj.pk}
            request = self.context.get('request')
            format = obj.media_file.name[obj.media_file.name.rindex('.') + 1:]

            return reverse('attachment-detail', kwargs=kwargs,
                           request=request, format=format)
