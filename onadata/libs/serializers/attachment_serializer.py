from rest_framework import serializers

from onadata.apps.logger.models.attachment import Attachment
from onadata.libs.serializers.fields.hyperlinked_multi_related_field import \
    HyperlinkedMultiRelatedField


class AttachmentSerializer(serializers.ModelSerializer):
    instance = HyperlinkedMultiRelatedField(
        view_name='data-detail',
        lookup_fields=(('pk', 'xform'), ('dataid', 'pk'))
    )

    class Meta:
        model = Attachment
        lookup_field = 'pk'
