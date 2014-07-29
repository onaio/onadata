from django.utils.translation import ugettext as _
from rest_framework import serializers

from onadata.apps.main.models.meta_data import MetaData

METADATA_TYPES = (
    ('data_license', _(u"Data License")),
    ('form_license', _(u"Form License")),
    ('mapbox_layer', _(u"Mapbox Layer")),
    ('media', _(u"Media")),
    ('public_link', _(u"Public Link")),
    ('source', _(u"Source")),
    ('supporting_doc', _(u"Supporting Document"))
)


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    xform = serializers.PrimaryKeyRelatedField()
    data_value = serializers.CharField(max_length=255,
                                       required=False)
    data_type = serializers.ChoiceField(choices=METADATA_TYPES)
    data_file = serializers.FileField(required=False)
    data_file_type = serializers.CharField(max_length=255, required=False)

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
