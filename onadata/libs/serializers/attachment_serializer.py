from rest_framework import serializers

from onadata.apps.logger.models.attachment import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='attachment-detail',
                                               lookup_field='pk')
    xform = serializers.Field(source='instance.xform.pk')
    data_id = serializers.Field(source='instance.pk')
    filename = serializers.Field(source='media_file.name')

    class Meta:
        fields = ('url', 'id', 'xform', 'data_id', 'mimetype', 'filename')
        lookup_field = 'pk'
        model = Attachment
