import mimetypes
import os
import requests

from contextlib import closing
from django.core.exceptions import ValidationError
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator
from django.db import models
from django.conf import settings
from hashlib import md5
from onadata.apps.logger.models import XForm

CHUNK_SIZE = 1024

urlvalidate = URLValidator()


def is_valid_url(uri):
    try:
        urlvalidate(uri)
    except ValidationError:
        return False

    return True


def upload_to(instance, filename):
    if instance.data_type == 'media':
        return os.path.join(
            instance.xform.user.username,
            'formid-media',
            filename
        )
    return os.path.join(
        instance.xform.user.username,
        'docs',
        filename
    )


def unique_type_for_form(xform, data_type, data_value=None, data_file=None):
    result = type_for_form(xform, data_type)
    if not len(result):
        result = MetaData(data_type=data_type, xform=xform)
        result.save()
    else:
        result = result[0]
    if data_value:
        result.data_value = data_value
        result.save()
    if data_file:
        if result.data_value is None or result.data_value == '':
            result.data_value = data_file.name
        result.data_file = data_file
        result.data_file_type = data_file.content_type
        result.save()
    return result


def type_for_form(xform, data_type):
    return MetaData.objects.filter(xform=xform, data_type=data_type)


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
    xform = models.ForeignKey(XForm)
    data_type = models.CharField(max_length=255)
    data_value = models.CharField(max_length=255)
    data_file = models.FileField(upload_to=upload_to, blank=True, null=True)
    data_file_type = models.CharField(max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        app_label = 'main'
        unique_together = ('xform', 'data_type', 'data_value')

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
                return u''
            else:
                self.file_hash = u'md5:%s' \
                    % md5(self.data_file.read()).hexdigest()

                return self.file_hash

        return u''

    @staticmethod
    def public_link(xform, data_value=None):
        data_type = 'public_link'
        if data_value is False:
            data_value = 'False'
        metadata = unique_type_for_form(xform, data_type, data_value)
        # make text field a boolean
        if metadata.data_value == 'True':
            return True
        else:
            return False

    @staticmethod
    def form_license(xform, data_value=None):
        data_type = 'form_license'
        return unique_type_for_form(xform, data_type, data_value)

    @staticmethod
    def data_license(xform, data_value=None):
        data_type = 'data_license'
        return unique_type_for_form(xform, data_type, data_value)

    @staticmethod
    def source(xform, data_value=None, data_file=None):
        data_type = 'source'
        return unique_type_for_form(xform, data_type, data_value, data_file)

    @staticmethod
    def supporting_docs(xform, data_file=None):
        data_type = 'supporting_doc'
        if data_file:
            doc = MetaData(data_type=data_type, xform=xform,
                           data_value=data_file.name,
                           data_file=data_file,
                           data_file_type=data_file.content_type)
            doc.save()
        return type_for_form(xform, data_type)

    @staticmethod
    def media_upload(xform, data_file=None, download=False):
        data_type = 'media'
        if data_file:
            allowed_types = settings.SUPPORTED_MEDIA_UPLOAD_TYPES
            content_type = data_file.content_type \
                if data_file.content_type in allowed_types else \
                mimetypes.guess_type(data_file.name)[0]
            if content_type in allowed_types:
                media = MetaData(data_type=data_type, xform=xform,
                                 data_value=data_file.name,
                                 data_file=data_file,
                                 data_file_type=content_type)
                media.save()
        return media_resources(type_for_form(xform, data_type), download)

    @staticmethod
    def media_add_uri(xform, uri):
        """Add a uri as a media resource"""
        data_type = 'media'

        if is_valid_url(uri):
            media = MetaData(data_type=data_type, xform=xform,
                             data_value=uri)
            media.save()

    @staticmethod
    def mapbox_layer_upload(xform, data=None):
        data_type = 'mapbox_layer'
        if data and not MetaData.objects.filter(xform=xform,
                                                data_type='mapbox_layer'):
            s = ''
            for key in data:
                s = s + data[key] + '||'
            mapbox_layer = MetaData(data_type=data_type, xform=xform,
                                    data_value=s)
            mapbox_layer.save()
        if type_for_form(xform, data_type):
            values = type_for_form(xform, data_type)[0].data_value.split('||')
            data_values = {}
            data_values['map_name'] = values[0]
            data_values['link'] = values[1]
            data_values['attribution'] = values[2]
            data_values['id'] = type_for_form(xform, data_type)[0].id
            return data_values
        else:
            return None

    @staticmethod
    def external_export(xform, data_value=None):
        data_type = 'external_export'

        if data_value:
            result = MetaData(data_type=data_type, xform=xform,
                              data_value=data_value)
            result.save()
            return result

        return MetaData.objects.filter(xform=xform, data_type=data_type)\
            .order_by('-id')

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
