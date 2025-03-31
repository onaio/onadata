# -*- coding: utf-8 -*-
"""
MetaData model
"""

from __future__ import unicode_literals

import hashlib
import importlib
import json
import logging
import mimetypes
import os
from collections import OrderedDict
from contextlib import closing

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator
from django.db import IntegrityError, models
from django.db.models.signals import post_delete, post_save
from django.utils import timezone

import requests

from onadata.libs.utils.cache_tools import (
    XFORM_MANIFEST_CACHE,
    XFORM_METADATA_CACHE,
    safe_delete,
)
from onadata.libs.utils.common_tags import (
    EXPORT_COLUMNS_REGISTER,
    GOOGLE_SHEET_DATA_TYPE,
    TEXTIT,
    TEXTIT_DETAILS,
    XFORM_META_PERMS,
)

ANONYMOUS_USERNAME = "anonymous"
CHUNK_SIZE = 1024
INSTANCE_MODEL_NAME = "instance"
PROJECT_MODEL_NAME = "project"
XFORM_MODEL_NAME = "xform"

DEFAULT_REQUEST_TIMEOUT = getattr(settings, "DEFAULT_REQUEST_TIMEOUT", 30)


def is_valid_url(uri):
    """
    Validates a URI.
    """
    try:
        URLValidator()(uri)
    except ValidationError:
        return False

    return True


def upload_to(instance, filename):
    """
    Returns the upload path for given ``filename``.
    """
    is_instance_model = instance.content_type.model == INSTANCE_MODEL_NAME
    username = None

    if instance.content_object.user is None and is_instance_model:
        username = instance.content_object.xform.user.username
    else:
        username = instance.content_object.user.username

    if instance.data_type == "media":
        return os.path.join(username, "formid-media", filename)

    return os.path.join(username, "docs", filename)


def save_metadata(metadata_obj):
    """
    Saves the MetaData object and returns it.
    """
    try:
        metadata_obj.save()
    except IntegrityError:
        logging.exception("MetaData object '%s' already exists", metadata_obj)

    return metadata_obj


def get_default_content_type():
    """
    Returns the default content type id for the XForm model.
    """
    content_object, _created = ContentType.objects.get_or_create(
        app_label="logger", model=XFORM_MODEL_NAME
    )

    return content_object.id


def unique_type_for_form(
    content_object, data_type, data_value=None, data_file=None, extra_data=None
):
    """
    Ensure that each metadata object has unique xform and data_type fields

    return the metadata object
    """
    defaults = {}

    if data_value:
        defaults["data_value"] = data_value

    if extra_data:
        defaults["extra_data"] = extra_data

    content_type = ContentType.objects.get_for_model(content_object)

    if data_value is None and data_file is None:
        # pylint: disable=no-member
        result = MetaData.objects.filter(
            object_id=content_object.id, content_type=content_type, data_type=data_type
        ).first()
    else:
        result, metadata_created = MetaData.objects.update_or_create(
            object_id=content_object.id,
            content_type=content_type,
            data_type=data_type,
            defaults=defaults,
        )

        # Force Django to recognize changes to extra_data by ensuring it always updates
        # During update, Django skips updating extra_data since it thinks the value
        # hasn't changed
        if not metadata_created and extra_data:
            result.extra_data = extra_data
            result.save()

    if data_file:
        if result.data_value is None or result.data_value == "":
            result.data_value = data_file.name
        result.data_file = data_file
        result.data_file_type = data_file.content_type
        result = save_metadata(result)

    return result


def type_for_form(content_object, data_type):
    """
    Returns the MetaData queryset for ``content_object`` of the given ``data_type``.
    """
    content_type = ContentType.objects.get_for_model(content_object)
    return MetaData.objects.filter(
        object_id=content_object.id, content_type=content_type, data_type=data_type
    )


def create_media(media):
    """Download media link"""
    if is_valid_url(media.data_value):
        filename = media.data_value.split("/")[-1]
        data_file = NamedTemporaryFile()
        content_type = mimetypes.guess_type(filename)
        with closing(
            requests.get(media.data_value, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
        ) as resp:
            # pylint: disable=no-member
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    data_file.write(chunk)
        data_file.seek(os.SEEK_SET, os.SEEK_END)
        size = os.path.getsize(data_file.name)
        data_file.seek(os.SEEK_SET)
        media.data_value = filename
        media.data_file = InMemoryUploadedFile(
            data_file, "data_file", filename, content_type, size, charset=None
        )

        return media

    return None


def media_resources(media_list, download=False):
    """List of MetaData objects of type media

    @param media_list - list of MetaData objects of type `media`
    @param download - boolean, when True downloads media files when
    media.data_value is a valid url

    return a list of MetaData objects

    """
    data = []
    for media in media_list:
        if media.data_file.name == "" and download:
            media = create_media(media)

            if media:
                data.append(media)
        else:
            data.append(media)

    return data


# pylint: disable=too-many-public-methods
class MetaData(models.Model):
    """MetaData class model."""

    data_type = models.CharField(max_length=255)
    data_value = models.CharField(max_length=255)
    extra_data = models.JSONField(default=dict, blank=True, null=True)
    data_file = models.FileField(upload_to=upload_to, blank=True, null=True)
    data_file_type = models.CharField(max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(null=True, auto_now_add=True)
    date_modified = models.DateTimeField(null=True, auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, default=get_default_content_type
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    objects = models.Manager()

    class Meta:
        app_label = "main"
        unique_together = ("object_id", "data_type", "data_value", "content_type")
        indexes = [
            models.Index(fields=["object_id", "data_type"]),
        ]

    # pylint: disable=arguments-differ
    def save(self, *args, **kwargs):
        self.set_hash()
        super().save(*args, **kwargs)

    @property
    def hash(self):
        """
        Returns the md5 hash of the metadata file.
        """
        if self.file_hash is not None and self.file_hash != "":
            return self.file_hash

        return self.set_hash()

    def set_hash(self):
        """
        Returns the md5 hash of the metadata file.
        """
        if not self.data_file:
            return None

        file_exists = self.data_file.storage.exists(self.data_file.name)

        if (file_exists and self.data_file.name != "") or (
            not file_exists and self.data_file
        ):
            try:
                self.data_file.seek(os.SEEK_SET)
            except IOError:
                pass
            else:
                file_hash = hashlib.new(
                    "md5", self.data_file.read(), usedforsecurity=False
                ).hexdigest()
                self.file_hash = f"md5:{file_hash}"

                return self.file_hash

        return ""

    def soft_delete(self):
        """
        Mark the MetaData as soft deleted,
        by updating the deleted_at field.
        """
        soft_deletion_time = timezone.now()
        self.deleted_at = soft_deletion_time
        self.save()

    def restore(self):
        """
        Restore the MetaData by setting the deleted_at field to None.
        """
        self.deleted_at = None
        self.save()

    @staticmethod
    def public_link(content_object, data_value=None):
        """Returns the public link metadata."""
        data_type = "public_link"
        if data_value is False:
            data_value = "False"
        metadata = unique_type_for_form(content_object, data_type, data_value)
        # make text field a boolean
        return metadata and metadata.data_value == "True"

    @staticmethod
    def set_google_sheet_details(content_object, data_value=None):
        """Returns Google Sheet details metadata object."""
        data_type = GOOGLE_SHEET_DATA_TYPE
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def get_google_sheet_details(obj):
        """
        Converts a metadata google sheet value, which contains data that is
        pipe separated, to a dictionary e.g 'valueA a | valueB b' to
        { 'valueA': 'a', 'valueB': 'b'}
        :param content_object_pk: xform primary key
        :return dictionary containing google sheet details
        """
        if isinstance(obj, str):
            metadata_data_value = obj
        else:
            metadata = MetaData.objects.filter(
                object_id=obj, data_type=GOOGLE_SHEET_DATA_TYPE
            ).first()
            metadata_data_value = metadata and metadata.data_value

        if metadata_data_value:
            data_list = metadata_data_value.split("|")
            if data_list:
                # the data_list format is something like ['A a', 'B b c'] and
                # the list comprehension and dict cast results to
                # {'A': 'a', 'B': 'b c'}
                return dict([tuple(a.strip().split(" ", 1)) for a in data_list])

        return metadata_data_value

    @staticmethod
    def published_by_formbuilder(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'published_by_formbuilder'
        """
        data_type = "published_by_formbuilder"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def enketo_url(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'enket_url'
        """
        data_type = "enketo_url"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def enketo_preview_url(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'enketo_preview_url'
        """
        data_type = "enketo_preview_url"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def enketo_single_submit_url(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'enketo_single_submit_url'
        """
        data_type = "enketo_single_submit_url"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def form_license(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'form_license'
        """
        data_type = "form_license"
        obj = unique_type_for_form(content_object, data_type, data_value)

        return obj.data_value if obj else None

    @staticmethod
    def data_license(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'data_license'
        """
        data_type = "data_license"
        obj = unique_type_for_form(content_object, data_type, data_value)

        return obj.data_value if obj else None

    @staticmethod
    def source(content_object, data_value=None, data_file=None):
        """
        Returns the metadata object where data_type is 'source'
        """
        data_type = "source"
        return unique_type_for_form(content_object, data_type, data_value, data_file)

    @staticmethod
    def supporting_docs(content_object, data_file=None):
        """
        Returns the metadata object where data_type is 'supporting_doc'
        """
        data_type = "supporting_doc"
        if data_file:
            content_type = ContentType.objects.get_for_model(content_object)

            _doc, _created = MetaData.objects.update_or_create(
                data_type=data_type,
                content_type=content_type,
                object_id=content_object.id,
                data_value=data_file.name,
                defaults={
                    "data_file": data_file,
                    "data_file_type": data_file.content_type,
                },
            )

        return type_for_form(content_object, data_type)

    @staticmethod
    def media_upload(content_object, data_file=None, download=False):
        """
        Returns the metadata object where data_type is 'media'
        """
        data_type = "media"
        if data_file:
            allowed_types = settings.SUPPORTED_MEDIA_UPLOAD_TYPES
            data_content_type = (
                data_file.content_type
                if data_file.content_type in allowed_types
                else mimetypes.guess_type(data_file.name)[0]
            )

            if data_content_type in allowed_types:
                content_type = ContentType.objects.get_for_model(content_object)

                _media, _created = MetaData.objects.update_or_create(
                    data_type=data_type,
                    content_type=content_type,
                    object_id=content_object.id,
                    data_value=data_file.name,
                    defaults={
                        "data_file": data_file,
                        "data_file_type": data_content_type,
                    },
                )
        return media_resources(type_for_form(content_object, data_type), download)

    @staticmethod
    def media_add_uri(content_object, uri):
        """Add a uri as a media resource"""
        data_type = "media"

        if is_valid_url(uri):
            _media, _created = MetaData.objects.update_or_create(
                data_type=data_type,
                data_value=uri,
                defaults={
                    "content_object": content_object,
                },
            )

    @staticmethod
    def mapbox_layer_upload(content_object, data=None):
        """
        Returns the metadata object where data_type is 'mapbox_layer'
        """
        data_type = "mapbox_layer"
        if data and not MetaData.objects.filter(
            object_id=content_object.id, data_type="mapbox_layer"
        ):
            data_value = ""
            for key in data:
                data_value = data_value + data[key] + "||"

            content_type = ContentType.objects.get_for_model(content_object)
            mapbox_layer = MetaData(
                data_type=data_type,
                content_type=content_type,
                object_id=content_object.id,
                data_value=data_value,
            )
            mapbox_layer.save()
        if type_for_form(content_object, data_type):
            values = type_for_form(content_object, data_type)[0].data_value.split("||")
            data_values = {}
            data_values["map_name"] = values[0]
            data_values["link"] = values[1]
            data_values["attribution"] = values[2]
            data_values["id"] = type_for_form(content_object, data_type)[0].id
            return data_values

        return None

    @staticmethod
    def external_export(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'external_export'
        """
        data_type = "external_export"

        if data_value:
            content_type = ContentType.objects.get_for_model(content_object)
            result = MetaData(
                data_type=data_type,
                content_type=content_type,
                object_id=content_object.id,
                data_value=data_value,
            )
            result.save()
            return result

        return MetaData.objects.filter(
            object_id=content_object.id, data_type=data_type
        ).order_by("-id")

    @property
    def external_export_url(self):
        """
        Returns the external export URL
        """
        parts = self.data_value.split("|")

        return parts[1] if len(parts) > 1 else None

    @property
    def external_export_name(self):
        """
        Returns the external export name
        """
        parts = self.data_value.split("|")

        return parts[0] if len(parts) > 1 else None

    @property
    def external_export_template(self):
        """
        Returns the exxernal export, "XLS report", template
        """
        parts = self.data_value.split("|")

        return parts[1].replace("xls", "templates") if len(parts) > 1 else None

    @staticmethod
    def textit(content_object, data_value=None):
        """Add a textit auth token flow uuid and default contact uuid"""
        data_type = TEXTIT
        obj = unique_type_for_form(content_object, data_type, data_value)

        return obj and obj.data_value

    @staticmethod
    def textit_flow_details(content_object, data_value: str = ""):
        """
        Returns the metadata object where data_type is 'textit_details'
        """
        data_type = TEXTIT_DETAILS
        return unique_type_for_form(content_object, data_type, data_value)

    @property
    def is_linked_dataset(self):
        """
        Returns True if the metadata object is a linked dataset.
        """
        return isinstance(self.data_value, str) and (
            self.data_value.startswith("xform")
            or self.data_value.startswith("dataview")
        )

    @staticmethod
    def xform_meta_permission(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'xform_meta_perms'
        """
        data_type = XFORM_META_PERMS

        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def submission_review(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'submission_review'
        """
        data_type = "submission_review"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def instance_csv_imported_by(content_object, data_value=None):
        """
        Returns the metadata object where data_type is 'imported_via_csv_by'
        """
        data_type = "imported_via_csv_by"
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def update_or_create_export_register(content_object, data_value=None):
        """Update or create export columns register for XForm."""
        # Avoid cyclic import by using importlib
        csv_builder = importlib.import_module("onadata.libs.utils.csv_builder")
        ordered_columns = OrderedDict()
        # pylint: disable=protected-access
        csv_builder.CSVDataFrameBuilder._build_ordered_columns(
            content_object._get_survey(), ordered_columns
        )
        serialized_columns = json.dumps(ordered_columns)
        data_type = EXPORT_COLUMNS_REGISTER
        extra_data = {
            "merged_multiples": serialized_columns,
            "split_multiples": serialized_columns,
        }
        data_value = "" if data_value is None else data_value
        return unique_type_for_form(
            content_object, data_type, data_value=data_value, extra_data=extra_data
        )


# pylint: disable=unused-argument,invalid-name
def clear_cached_metadata_instance_object(
    sender, instance=None, created=False, **kwargs
):
    """
    Clear the cache for the metadata object.
    """
    xform_id = instance.object_id
    safe_delete(f"{XFORM_METADATA_CACHE}{xform_id}")

    if instance.data_type == "media":
        safe_delete(f"{XFORM_MANIFEST_CACHE}{xform_id}")


# pylint: disable=unused-argument
def update_attached_object(sender, instance=None, created=False, **kwargs):
    """
    Save the content_object attached to a MetaData instance.
    """
    if instance:
        instance.content_object.save()


post_save.connect(
    clear_cached_metadata_instance_object,
    sender=MetaData,
    dispatch_uid="clear_cached_metadata_instance_object",
)
post_save.connect(
    update_attached_object, sender=MetaData, dispatch_uid="update_attached_xform"
)
post_delete.connect(
    clear_cached_metadata_instance_object,
    sender=MetaData,
    dispatch_uid="clear_cached_metadata_instance_delete",
)
