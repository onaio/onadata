from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.main.models.meta_data import MetaData

METADATA_TYPES = (
    ('media', _(u"Media")),
    ('public_link', _(u"Public Link")),
    ('form_license', _(u"Form License")),
    ('data_license', _(u"Data License")),
    ('source', _(u"Source")),
    ('supporting_doc', _(u"Supporting Document"))
)


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    xform = serializers.PrimaryKeyRelatedField(source='xform')
    data_value = serializers.CharField(max_length=255, source='data_value',
                                       required=False)
    data_type = serializers.ChoiceField(
        choices=METADATA_TYPES, source='data_type')

    class Meta:
        model = MetaData

    def restore_object(self, attrs, instance=None):
        data_type = attrs.get('data_type')
        data_file = attrs.get('data_file')
        xform = attrs.get('xform')
        data_value = data_file.name if data_file else attrs.get('data_value')
        data_file_type = data_file.content_type if data_file else None

        if instance:
            return super(MetaDataSerializer, self).restore_object(
                attrs, instance)

        return MetaData(
            data_type=data_type,
            xform=xform,
            data_value=data_value,
            data_file=data_file,
            data_file_type=data_file_type
        )
