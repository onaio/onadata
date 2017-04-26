from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.logger.models import DataView
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.main.models import MetaData
from onadata.libs.utils.common_tags import XFORM_META_PERMS
from onadata.libs.permissions import ROLES
from onadata.libs.permissions import ManagerRole
from onadata.libs.serializers.fields.xform_related_field import (
    XFormRelatedField,)
from onadata.libs.serializers.fields.project_related_field import (
    ProjectRelatedField,)
from onadata.libs.serializers.fields.instance_related_field import (
    InstanceRelatedField,)
from onadata.apps.api.tools import update_role_by_meta_xform_perms

UNIQUE_TOGETHER_ERROR = u"Object already exists"

CSV_CONTENT_TYPE = 'text/csv'
MEDIA_TYPE = 'media'
DOC_TYPE = 'supporting_doc'
METADATA_TYPES = (
    ('data_license', _(u"Data License")),
    ('enketo_preview_url', _(u"Enketo Preview URL")),
    ('enketo_url', _(u"Enketo URL")),
    ('form_license', _(u"Form License")),
    ('mapbox_layer', _(u"Mapbox Layer")),
    (MEDIA_TYPE, _(u"Media")),
    ('public_link', _(u"Public Link")),
    ('source', _(u"Source")),
    (DOC_TYPE, _(u"Supporting Document")),
    ('external_export', _(u"External Export")),
    ('textit', _(u"External Export")),
    ('google_sheets', _(u"Google Sheet")),
    ('xform_meta_perms', _("Xform meta permissions"))
)

DATAVIEW_TAG = 'dataview'
XFORM_TAG = 'xform'

PROJECT_METADATA_TYPES = (
    (MEDIA_TYPE, _(u"Media")),
    ('supporting_doc', _(u"Supporting Document")))


def get_linked_object(parts):
    """Returns an XForm or DataView object

    Raises 404 Exception if object  is not found.
    Raises serializers.ValidationError if the format of the linked
    object is not valid.
    """
    if isinstance(parts, list) and len(parts):
        obj_type = parts[0]
        if obj_type in [DATAVIEW_TAG, XFORM_TAG] and len(parts) > 1:
            pk = parts[1]
            try:
                pk = int(pk)
            except ValueError:
                raise serializers.ValidationError({
                    'data_value':
                    _(u"Invalid %(type)s id %(id)s." %
                      {'type': obj_type, 'id': pk})
                })
            else:
                model = DataView if obj_type == DATAVIEW_TAG else XForm

                return get_object_or_404(model, pk=pk)


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.ReadOnlyField()
    xform = XFormRelatedField(
        queryset=XForm.objects.all(),
        required=False
    )
    project = ProjectRelatedField(
        queryset=Project.objects.all(),
        required=False
    )
    instance = InstanceRelatedField(
        queryset=Instance.objects.all(),
        required=False)
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
        fields = ('id', 'xform', 'project', 'instance', 'data_value',
                  'data_type', 'data_file', 'data_file_type', 'media_url',
                  'file_hash', 'url', 'date_created')

    def get_media_url(self, obj):
        if obj.data_type in [DOC_TYPE, MEDIA_TYPE] and\
                getattr(obj, "data_file") and getattr(obj.data_file, "url"):
            return obj.data_file.url
        elif obj.data_type in [MEDIA_TYPE] and obj.is_linked_dataset:
            kwargs = {
                'kwargs': {
                    'pk': obj.content_object.pk,
                    'username': obj.content_object.user.username,
                    'metadata': obj.pk
                },
                'request': self.context.get('request'),
                'format': 'csv'
            }

            return reverse('xform-media', **kwargs)

    def validate(self, attrs):
        """
        Validate url if we are adding a media uri instead of a media file
        """
        value = attrs.get('data_value')
        data_type = attrs.get('data_type')
        data_file = attrs.get('data_file')

        if not ('project' in attrs or 'xform' in attrs or 'instance' in attrs):
            raise serializers.ValidationError({
                'missing_field': _(u"`xform` or `project` or `instance`"
                                   "field is required.")
            })

        if data_type == 'media' and data_file is None:
            try:
                URLValidator()(value)
            except ValidationError:
                parts = value.split()
                if len(parts) < 3:
                    raise serializers.ValidationError({
                        'data_value': _(
                            u"Expecting 'xform [xform id] [media name]' "
                            "or 'dataview [dataview id] [media name]' "
                            "or a valid URL."
                        )
                    })
                obj = get_linked_object(parts)
                if obj:
                    xform = obj.xform if isinstance(obj, DataView) else obj
                    request = self.context['request']
                    user_has_role = ManagerRole.user_has_role
                    has_perm = user_has_role(request.user, xform) or \
                        user_has_role(request.user, obj.project)
                    if not has_perm:
                        raise serializers.ValidationError({
                            'data_value':
                            _(u"User has no permission to "
                                "the dataview.")
                        })
                else:
                    raise serializers.ValidationError({
                        'data_value': _(u"Invalid url '%s'." % value)
                    })

        if data_type == XFORM_META_PERMS:
            perms = value.split('|')
            if len(perms) != 2 or not set(perms).issubset(set(ROLES.keys())):
                raise serializers.ValidationError(
                    _(u"Format 'role'|'role' or Invalid role"))

        return attrs

    def get_content_object(self, validated_data):

        if validated_data:
            return (validated_data.get('xform') or
                    validated_data.get('project') or
                    validated_data.get('instance'))

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

        try:
            if data_type == XFORM_META_PERMS:
                metadata = \
                    MetaData.xform_meta_permission(content_object,
                                                   data_value=data_value)
                update_role_by_meta_xform_perms(content_object)

            else:

                metadata = MetaData.objects.create(
                    content_type=content_type,
                    data_type=data_type,
                    data_value=data_value,
                    data_file=data_file,
                    data_file_type=data_file_type,
                    object_id=content_object.id
                )

            return metadata
        except IntegrityError:
            raise serializers.ValidationError(_(UNIQUE_TOGETHER_ERROR))

    def update(self, instance, validated_data):
        instance = super(MetaDataSerializer, self).update(instance,
                                                          validated_data)

        if instance.data_type == XFORM_META_PERMS:
            update_role_by_meta_xform_perms(instance.content_object)

        return instance
