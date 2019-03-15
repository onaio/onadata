from __future__ import unicode_literals

import logging
import mimetypes
import os
from contextlib import closing
from hashlib import md5

import requests
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator
from django.db import IntegrityError, models
from django.db.models.signals import post_delete, post_save
from past.builtins import basestring

from onadata.libs.utils.cache_tools import XFORM_METADATA_CACHE, safe_delete
from onadata.libs.utils.common_tags import (GOOGLE_SHEET_DATA_TYPE, TEXTIT,
                                            XFORM_META_PERMS)

CHUNK_SIZE = 1024
INSTANCE_MODEL_NAME = "instance"
PROJECT_MODEL_NAME = "project"
XFORM_MODEL_NAME = "xform"


urlvalidate = URLValidator()

ANONYMOUS_USERNAME = "anonymous"


def is_valid_url(uri):
    try:
        urlvalidate(uri)
    except ValidationError:
        return False

    return True


def upload_to(instance, filename):
    username = None

    if instance.content_object.user is None and \
            instance.content_type.model == INSTANCE_MODEL_NAME:
        username = instance.content_object.xform.user.username
    else:
        username = instance.content_object.user.username

    if instance.data_type == 'media':
        return os.path.join(username, 'formid-media', filename)

    return os.path.join(username, 'docs', filename)


def save_metadata(metadata_obj):
    try:
        metadata_obj.save()
    except IntegrityError:
        logging.exception("MetaData object '%s' already exists" % metadata_obj)

    return metadata_obj


def get_default_content_type():
    content_object, created = ContentType.objects.get_or_create(
        app_label="logger", model=XFORM_MODEL_NAME)

    return content_object.id


def unique_type_for_form(content_object,
                         data_type,
                         data_value=None,
                         data_file=None):
    """
    Ensure that each metadata object has unique xform and data_type fields

    return the metadata object
    """
    defaults = {'data_value': data_value} if data_value else {}
    content_type = ContentType.objects.get_for_model(content_object)

    if data_value is None and data_file is None:
        result = MetaData.objects.filter(
            object_id=content_object.id, content_type=content_type,
            data_type=data_type).first()
    else:
        result, created = MetaData.objects.update_or_create(
            object_id=content_object.id, content_type=content_type,
            data_type=data_type, defaults=defaults)

    if data_file:
        if result.data_value is None or result.data_value == '':
            result.data_value = data_file.name
        result.data_file = data_file
        result.data_file_type = data_file.content_type
        result = save_metadata(result)

    return result


def type_for_form(content_object, data_type):
    content_type = ContentType.objects.get_for_model(content_object)
    return MetaData.objects.filter(object_id=content_object.id,
                                   content_type=content_type,
                                   data_type=data_type)


def create_media(media):
    """Download media link"""
    if is_valid_url(media.data_value):
        filename = media.data_value.split('/')[-1]
        data_file = NamedTemporaryFile()
        content_type = mimetypes.guess_type(filename)
        with closing(requests.get(media.data_value, stream=True)) as r:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    data_file.write(chunk)
        data_file.seek(os.SEEK_SET, os.SEEK_END)
        size = os.path.getsize(data_file.name)
        data_file.seek(os.SEEK_SET)
        media.data_value = filename
        media.data_file = InMemoryUploadedFile(
            data_file, 'data_file', filename, content_type,
            size, charset=None)

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
        if media.data_file.name == '' and download:
            media = create_media(media)

            if media:
                data.append(media)
        else:
            data.append(media)

    return data


class MetaData(models.Model):
    data_type = models.CharField(max_length=255)
    data_value = models.CharField(max_length=255)
    data_file = models.FileField(upload_to=upload_to, blank=True, null=True)
    data_file_type = models.CharField(max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(null=True, auto_now_add=True)
    date_modified = models.DateTimeField(null=True, auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                     default=get_default_content_type)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    objects = models.Manager()

    class Meta:
        app_label = 'main'
        unique_together = ('object_id', 'data_type', 'data_value',
                           'content_type')

    def save(self, *args, **kwargs):
        self._set_hash()
        super(MetaData, self).save(*args, **kwargs)

    @property
    def hash(self):
        if self.file_hash is not None and self.file_hash != '':
            return self.file_hash
        else:
            return self._set_hash()

    def _set_hash(self):
        if not self.data_file:
            return None

        file_exists = self.data_file.storage.exists(self.data_file.name)

        if (file_exists and self.data_file.name != '') \
                or (not file_exists and self.data_file):
            try:
                self.data_file.seek(os.SEEK_SET)
            except IOError:
                return ''
            else:
                self.file_hash = 'md5:%s' % md5(
                    self.data_file.read()).hexdigest()

                return self.file_hash

        return ''

    @staticmethod
    def public_link(content_object, data_value=None):
        data_type = 'public_link'
        if data_value is False:
            data_value = 'False'
        metadata = unique_type_for_form(content_object, data_type, data_value)
        # make text field a boolean
        return metadata and metadata.data_value == 'True'

    @staticmethod
    def set_google_sheet_details(content_object, data_value=None):
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
        if isinstance(obj, basestring):
            metadata_data_value = obj
        else:
            metadata = MetaData.objects.filter(
                object_id=obj, data_type=GOOGLE_SHEET_DATA_TYPE
            ).first()
            metadata_data_value = metadata and metadata.data_value

        if metadata_data_value:
            data_list = metadata_data_value.split('|')
            if data_list:
                # the data_list format is something like ['A a', 'B b c'] and
                # the list comprehension and dict cast results to
                # {'A': 'a', 'B': 'b c'}
                return dict(
                    [tuple(a.strip().split(' ', 1)) for a in data_list])

    @staticmethod
    def published_by_formbuilder(content_object, data_value=None):
        data_type = 'published_by_formbuilder'
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def enketo_url(content_object, data_value=None):
        data_type = 'enketo_url'
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def enketo_preview_url(content_object, data_value=None):
        data_type = 'enketo_preview_url'
        return unique_type_for_form(content_object, data_type, data_value)

    @staticmethod
    def form_license(content_object, data_value=None):
        data_type = 'form_license'
        obj = unique_type_for_form(content_object, data_type, data_value)

        return (obj and obj.data_value) or None

    @staticmethod
    def data_license(content_object, data_value=None):
        data_type = 'data_license'
        obj = unique_type_for_form(content_object, data_type, data_value)

        return (obj and obj.data_value) or None

    @staticmethod
    def source(content_object, data_value=None, data_file=None):
        data_type = 'source'
        return unique_type_for_form(
            content_object, data_type, data_value, data_file)

    @staticmethod
    def supporting_docs(content_object, data_file=None):
        data_type = 'supporting_doc'
        if data_file:
            content_type = ContentType.objects.get_for_model(content_object)

            doc, created = MetaData.objects.update_or_create(
                data_type=data_type,
                content_type=content_type,
                object_id=content_object.id,
                data_value=data_file.name,
                defaults={
                    'data_file': data_file,
                    'data_file_type': data_file.content_type
                })

        return type_for_form(content_object, data_type)

    @staticmethod
    def media_upload(content_object, data_file=None, download=False):
        data_type = 'media'
        if data_file:
            allowed_types = settings.SUPPORTED_MEDIA_UPLOAD_TYPES
            data_content_type = data_file.content_type \
                if data_file.content_type in allowed_types else \
                mimetypes.guess_type(data_file.name)[0]

            if data_content_type in allowed_types:
                content_type = ContentType.objects.get_for_model(
                    content_object)

                media, created = MetaData.objects.update_or_create(
                    data_type=data_type,
                    content_type=content_type,
                    object_id=content_object.id,
                    data_value=data_file.name,
                    defaults={
                        'data_file': data_file,
                        'data_file_type': data_content_type
                    })
        return media_resources(
            type_for_form(content_object, data_type), download)

    @staticmethod
    def media_add_uri(content_object, uri):
        """Add a uri as a media resource"""
        data_type = 'media'

        if is_valid_url(uri):
            media, created = MetaData.objects.update_or_create(
                data_type=data_type,
                data_value=uri,
                defaults={
                    'content_object': content_object,
                })

    @staticmethod
    def mapbox_layer_upload(content_object, data=None):
        data_type = 'mapbox_layer'
        if data and not MetaData.objects.filter(object_id=content_object.id,
                                                data_type='mapbox_layer'):
            s = ''
            for key in data:
                s = s + data[key] + '||'

            content_type = ContentType.objects.get_for_model(content_object)
            mapbox_layer = MetaData(data_type=data_type,
                                    content_type=content_type,
                                    object_id=content_object.id,
                                    data_value=s)
            mapbox_layer.save()
        if type_for_form(content_object, data_type):
            values = type_for_form(
                content_object, data_type)[0].data_value.split('||')
            data_values = {}
            data_values['map_name'] = values[0]
            data_values['link'] = values[1]
            data_values['attribution'] = values[2]
            data_values['id'] = type_for_form(content_object, data_type)[0].id
            return data_values
        else:
            return None

    @staticmethod
    def external_export(content_object, data_value=None):
        data_type = 'external_export'

        if data_value:
            content_type = ContentType.objects.get_for_model(content_object)
            result = MetaData(data_type=data_type,
                              content_type=content_type,
                              object_id=content_object.id,
                              data_value=data_value)
            result.save()
            return result

        return MetaData.objects.filter(
            object_id=content_object.id, data_type=data_type).order_by('-id')

    @property
    def external_export_url(self):
        parts = self.data_value.split('|')

        return parts[1] if len(parts) > 1 else None

    @property
    def external_export_name(self):
        parts = self.data_value.split('|')

        return parts[0] if len(parts) > 1 else None

    @property
    def external_export_template(self):
        parts = self.data_value.split('|')

        return parts[1].replace('xls', 'templates') if len(parts) > 1 else None

    @staticmethod
    def textit(content_object, data_value=None):
        """Add a textit auth token flow uuid and default contact uuid"""
        data_type = TEXTIT
        obj = unique_type_for_form(content_object, data_type, data_value)

        return obj and obj.data_value

    @property
    def is_linked_dataset(self):
        return (
            isinstance(self.data_value, basestring) and
            (self.data_value.startswith('xform') or
             self.data_value.startswith('dataview'))
        )

    @staticmethod
    def xform_meta_permission(content_object, data_value=None):
        data_type = XFORM_META_PERMS

        return unique_type_for_form(
            content_object, data_type, data_value)

    @staticmethod
    def submission_review(content_object, data_value=None):
        data_type = 'submission_review'
        return unique_type_for_form(content_object, data_type, data_value)


def clear_cached_metadata_instance_object(
        sender, instance=None, created=False, **kwargs):
    safe_delete('{}{}'.format(
        XFORM_METADATA_CACHE, instance.object_id))


def update_attached_object(sender, instance=None, created=False, **kwargs):
    if instance:
        instance.content_object.save()


post_save.connect(clear_cached_metadata_instance_object, sender=MetaData,
                  dispatch_uid='clear_cached_metadata_instance_object')
post_save.connect(update_attached_object, sender=MetaData,
                  dispatch_uid='update_attached_xform')
post_delete.connect(clear_cached_metadata_instance_object, sender=MetaData,
                    dispatch_uid='clear_cached_metadata_instance_delete')
