from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import ugettext as _

from rest_framework import serializers

from onadata.apps.logger.models import XForm, Project
from onadata.apps.main.models import MetaData

from onadata.libs.serializers.fields.xform_related_field import (
    XFormRelatedField,)
from onadata.libs.serializers.fields.project_related_field import (
    ProjectRelatedField,)

CSV_CONTENT_TYPE = 'text/csv'
MEDIA_TYPE = 'media'
METADATA_TYPES = (
    ('data_license', _(u"Data License")),
    ('enketo_preview_url', _(u"Enketo Preview URL")),
    ('enketo_url', _(u"Enketo URL")),
    ('form_license', _(u"Form License")),
    ('mapbox_layer', _(u"Mapbox Layer")),
    (MEDIA_TYPE, _(u"Media")),
    ('public_link', _(u"Public Link")),
    ('source', _(u"Source")),
    ('supporting_doc', _(u"Supporting Document")),
    ('external_export', _(u"External Export")),
    ('textit', _(u"External Export"))
)

PROJECT_METADATA_TYPES = (
    (MEDIA_TYPE, _(u"Media")),
    ('supporting_doc', _(u"Supporting Document")))


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField()
    xform = XFormRelatedField(queryset=XForm.objects.all())
    project = ProjectRelatedField(queryset=Project.objects.all())
    data_value = serializers.CharField(max_length=255,
                                       required=True)
    data_type = serializers.ChoiceField(choices=METADATA_TYPES)
    data_file = serializers.FileField(required=False)
    data_file_type = serializers.CharField(max_length=255, required=False,
                                           allow_blank=True)
    media_url = serializers.SerializerMethodField()
    date_created = serializers.ReadOnlyField()

    _xform_field = None
    _project_field = None

    class Meta:
        model = MetaData
        fields = ('id', 'xform', 'project', 'data_value', 'data_type',
                  'data_file', 'data_file_type', 'media_url', 'file_hash',
                  'url', 'date_created')

    def get_media_url(self, obj):
        if obj.data_type == MEDIA_TYPE and getattr(obj, "data_file") \
                and getattr(obj.data_file, "url"):
            return obj.data_file.url

        return None

    def validate(self, attrs):
        """
        Validate url if we are adding a media uri instead of a media file
        """
        value = attrs.get('data_value')
        media = attrs.get('data_type')
        data_file = attrs.get('data_file')

        if media == 'media' and data_file is None:
            try:
                URLValidator()(value)
            except ValidationError:
                raise serializers.ValidationError({
                    'data_value': _(u"Invalid url %s." % value)
                })

        return attrs

    def get_content_object(self, validated_data):

        if validated_data:
            return validated_data.get('xform') or validated_data.get('project')

    def create(self, validated_data):
        data_type = validated_data.get('data_type')
        data_file = validated_data.get('data_file')

        content_object = self.get_content_object(validated_data)
        data_value = data_file.name \
            if data_file else validated_data.get('data_value')
        data_file_type = data_file.content_type if data_file else None

        # not exactly sure what changed in the requests.FILES for django 1.7
        # csv files uploaded in windows do not have the text/csv content_type
        # this works around that
        if data_type == MEDIA_TYPE and data_file \
                and data_file.name.lower().endswith('.csv') \
                and data_file_type != CSV_CONTENT_TYPE:
            data_file_type = CSV_CONTENT_TYPE

        content_type = ContentType.objects.get_for_model(content_object)
        print("[debug] - content_type - {}".format(content_type))

        return MetaData.objects.create(
            content_type=content_type,
            data_type=data_type,
            data_value=data_value,
            data_file=data_file,
            data_file_type=data_file_type,
            object_id=content_object.id
        )

    def to_internal_value(self, data):

        if data.get("xform"):
            self._project_field = self.fields.fields.pop("project")

            if self.fields.fields.get("xform") is None:
                self.fields.fields['xform'] = self._xform_field

        if data.get("project"):
            self._xform_field = self.fields.fields.pop("xform")

            if self.fields.fields.get("project") is None:
                self.fields.fields['project'] = self._project_field

        return super(MetaDataSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        fields = self.fields.fields

        if isinstance(instance.content_object, XForm)\
                and fields.get("project"):
            self._project_field = self.fields.fields.pop("project")

            if self.fields.fields.get("xform") is None:
                self.fields.fields['xform'] = self._xform_field

        elif isinstance(instance.content_object, Project)\
                and fields.get("xform"):
            self._xform_field = self.fields.fields.pop("xform")

            if self.fields.fields.get("project") is None:
                self.fields.fields['project'] = self._project_field

        return super(MetaDataSerializer, self).to_representation(instance)
