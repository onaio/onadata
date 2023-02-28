# -*- coding: utf-8 -*-
"""
MetaData Serializer
"""

import mimetypes
import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from rest_framework import serializers
from rest_framework.reverse import reverse
from six.moves.urllib.parse import urlparse

from onadata.apps.api.tools import update_role_by_meta_xform_perms
from onadata.apps.logger.models import DataView, Instance, Project, XForm
from onadata.apps.main.models import MetaData
from onadata.libs.permissions import ROLES, ManagerRole
from onadata.libs.serializers.fields.instance_related_field import InstanceRelatedField
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.fields.project_related_field import ProjectRelatedField
from onadata.libs.serializers.fields.xform_related_field import XFormRelatedField
from onadata.libs.utils.api_export_tools import get_metadata_format
from onadata.libs.utils.common_tags import (
    IMPORTED_VIA_CSV_BY,
    SUBMISSION_REVIEW,
    XFORM_META_PERMS,
)
from onadata.libs.utils.image_tools import is_azure_storage, generate_media_url_with_sas

UNIQUE_TOGETHER_ERROR = "Object already exists"

CSV_CONTENT_TYPE = "text/csv"
MEDIA_TYPE = "media"
DOC_TYPE = "supporting_doc"
METADATA_TYPES = (
    ("data_license", _("Data License")),
    ("enketo_preview_url", _("Enketo Preview URL")),
    ("enketo_url", _("Enketo URL")),
    ("form_license", _("Form License")),
    ("mapbox_layer", _("Mapbox Layer")),
    (MEDIA_TYPE, _("Media")),
    ("public_link", _("Public Link")),
    ("source", _("Source")),
    (DOC_TYPE, _("Supporting Document")),
    ("external_export", _("External Export")),
    ("textit", _("TextIt")),
    ("google_sheets", _("Google Sheet")),
    ("xform_meta_perms", _("Xform meta permissions")),
    ("submission_review", _("Submission Review")),
    (IMPORTED_VIA_CSV_BY, _("Imported via CSV by")),
)  # yapf:disable

DATAVIEW_TAG = "dataview"
XFORM_TAG = "xform"

PROJECT_METADATA_TYPES = (
    (MEDIA_TYPE, _("Media")),
    ("supporting_doc", _("Supporting Document")),
)


def get_linked_object(parts):
    """Returns an XForm or DataView object

    Raises 404 Exception if object  is not found.
    Raises serializers.ValidationError if the format of the linked
    object is not valid.
    """
    if isinstance(parts, list) and parts:
        obj_type = parts[0]
        if "geojson" in obj_type:
            obj_type = obj_type.split("_")[0]
        if obj_type in [DATAVIEW_TAG, XFORM_TAG] and len(parts) > 1:
            obj_pk = parts[1]
            try:
                obj_pk = int(obj_pk)
            except ValueError as e:
                raise serializers.ValidationError(
                    {
                        "data_value": _(
                            "Invalid %(type)s id %(id)s."
                            % {"type": obj_type, "id": obj_pk}
                        )
                    }
                ) from e
            else:
                model = DataView if obj_type == DATAVIEW_TAG else XForm

                return get_object_or_404(model, pk=obj_pk)
    return None


class MetaDataSerializer(serializers.HyperlinkedModelSerializer):
    """
    MetaData HyperlinkedModelSerializer
    """

    id = serializers.ReadOnlyField()  # pylint: disable=invalid-name
    xform = XFormRelatedField(queryset=XForm.objects.all(), required=False)
    project = ProjectRelatedField(queryset=Project.objects.all(), required=False)
    instance = InstanceRelatedField(queryset=Instance.objects.all(), required=False)
    data_value = serializers.CharField(max_length=255, required=True)
    data_type = serializers.ChoiceField(choices=METADATA_TYPES)
    data_file = serializers.FileField(required=False)
    extra_data = JsonField(required=False)
    data_file_type = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    media_url = serializers.SerializerMethodField()
    date_created = serializers.ReadOnlyField()

    _xform_field = None
    _project_field = None

    class Meta:
        model = MetaData
        fields = (
            "id",
            "xform",
            "project",
            "instance",
            "data_value",
            "data_type",
            "data_file",
            "extra_data",
            "data_file_type",
            "media_url",
            "file_hash",
            "url",
            "date_created",
        )

    def get_media_url(self, obj):
        """
        Returns media URL for given metadata
        """
        if (
            obj.data_type in [DOC_TYPE, MEDIA_TYPE]
            and getattr(obj, "data_file")
            and getattr(obj.data_file, "url")
        ):
            media_name = obj.data_file.name
            return (
                generate_media_url_with_sas(media_name)
                if media_name and is_azure_storage()
                else obj.data_file.url
            )
        if obj.data_type in [MEDIA_TYPE] and obj.is_linked_dataset:
            request = self.context.get("request")
            kwargs = {
                "kwargs": {
                    "pk": obj.content_object.pk,
                    "username": obj.content_object.user.username,
                    "metadata": obj.pk,
                },
                "request": request,
                "format": get_metadata_format(obj.data_value),
            }

            return reverse("xform-media", **kwargs)
        return None

    # pylint: disable=too-many-branches
    def validate(self, attrs):
        """
        Validate url if we are adding a media uri instead of a media file
        """
        value = attrs.get("data_value")
        data_type = attrs.get("data_type")
        data_file = attrs.get("data_file")

        if not ("project" in attrs or "xform" in attrs or "instance" in attrs):
            raise serializers.ValidationError(
                {
                    "missing_field": _(
                        "`xform` or `project` or `instance` field is required."
                    )
                }
            )

        if data_file:
            allowed_types = settings.SUPPORTED_MEDIA_UPLOAD_TYPES
            # add geojson mimetype
            mimetypes.add_type("application/geo+json", ".geojson")
            data_content_type = (
                data_file.content_type
                if data_file.content_type in allowed_types
                else mimetypes.guess_type(data_file.name)[0]
            )
            if data_content_type not in allowed_types:
                raise serializers.ValidationError(
                    {"data_file": _(f"Unsupported media file type {data_content_type}")}
                )
            attrs["data_file_type"] = data_content_type

        if data_type == "media" and data_file is None:
            try:
                URLValidator()(value)
            except ValidationError as e:
                parts = value.split()
                if len(parts) < 3:
                    raise serializers.ValidationError(
                        {
                            "data_value": _(
                                "Expecting 'xform [xform id] [media name]' "
                                "or 'dataview [dataview id] [media name]' "
                                "or a valid URL."
                            )
                        }
                    )
                obj = get_linked_object(parts)
                if obj:
                    xform = obj.xform if isinstance(obj, DataView) else obj
                    request = self.context["request"]
                    user_has_role = ManagerRole.user_has_role
                    has_perm = user_has_role(request.user, xform) or user_has_role(
                        request.user, obj.project
                    )
                    if not has_perm:
                        raise serializers.ValidationError(
                            {"data_value": _("User has no permission to the dataview.")}
                        ) from e
                else:
                    raise serializers.ValidationError(
                        {"data_value": _(f"Invalid url '{value}'.")}
                    ) from e
            else:
                # check if we have a value for the filename.
                if not os.path.basename(urlparse(value).path):
                    raise serializers.ValidationError(
                        {
                            "data_value": _(
                                f"Cannot get filename from URL {value}. URL should "
                                "include the filename e.g "
                                "http://example.com/data.csv"
                            )
                        }
                    )

        if data_type == XFORM_META_PERMS:
            perms = value.split("|")
            if len(perms) != 2 or not set(perms).issubset(set(ROLES)):
                raise serializers.ValidationError(
                    _("Format 'role'|'role' or Invalid role")
                )

        return attrs

    def get_content_object(self, validated_data):
        """
        Returns the validated 'xform' or 'project' or 'instance' ids being
        linked to the metadata.
        """

        if validated_data:
            return (
                validated_data.get("xform")
                or validated_data.get("project")
                or validated_data.get("instance")
            )
        return None

    def create(self, validated_data):
        data_type = validated_data.get("data_type")
        data_file = validated_data.get("data_file")
        data_file_type = validated_data.get("data_file_type")
        extra_data = validated_data.get("extra_data")

        content_object = self.get_content_object(validated_data)
        data_value = data_file.name if data_file else validated_data.get("data_value")

        # not exactly sure what changed in the requests.FILES for django 1.7
        # csv files uploaded in windows do not have the text/csv content_type
        # this works around that
        if (
            data_type == MEDIA_TYPE
            and data_file
            and data_file.name.lower().endswith(".csv")
            and data_file_type != CSV_CONTENT_TYPE
        ):
            data_file_type = CSV_CONTENT_TYPE

        content_type = ContentType.objects.get_for_model(content_object)

        try:
            if data_type == XFORM_META_PERMS:
                metadata = MetaData.xform_meta_permission(
                    content_object, data_value=data_value
                )
                update_role_by_meta_xform_perms(content_object)

            elif data_type == SUBMISSION_REVIEW:
                # ensure only one submission_review metadata exists per form
                if MetaData.submission_review(content_object):
                    raise serializers.ValidationError(_(UNIQUE_TOGETHER_ERROR))
                metadata = MetaData.submission_review(
                    content_object, data_value=data_value
                )
            elif data_type == IMPORTED_VIA_CSV_BY:
                metadata = MetaData.instance_csv_imported_by(
                    content_object, data_value=data_value
                )
            else:
                metadata = MetaData.objects.create(
                    content_type=content_type,
                    data_type=data_type,
                    data_value=data_value,
                    data_file=data_file,
                    extra_data=extra_data,
                    data_file_type=data_file_type,
                    object_id=content_object.id,
                )

            return metadata
        except IntegrityError as e:
            raise serializers.ValidationError(_(UNIQUE_TOGETHER_ERROR)) from e
        return None

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)

        if instance.data_type == XFORM_META_PERMS:
            update_role_by_meta_xform_perms(instance.content_object)

        return instance
