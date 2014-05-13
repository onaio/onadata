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

urlvalidate = URLValidator()


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


def media_resources(media_list):
    data = []
    for media in media_list:
        if media.data_file.name == '':
            try:
                urlvalidate(media.data_value)
            except ValidationError:
                pass
            else:
                filename = media.data_value.split('/')[-1]
                data_file = NamedTemporaryFile()
                content_type = mimetypes.guess_type(filename)
                with closing(requests.get(media.data_value, stream=True)) as r:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            data_file.write(chunk)
                data_file.seek(0, 2)
                size = os.path.getsize(data_file.name)
                data_file.seek(0)
                media.data_value = filename
                media.data_file = InMemoryUploadedFile(
                    data_file, 'data_file', filename, content_type,
                    size, charset=None)
                data.append(media)
        else:
            data.append(media)

    return data


class MetaData(models.Model):
    xform = models.ForeignKey(XForm)
    data_type = models.CharField(max_length=255)
    data_value = models.CharField(max_length=255)
    data_file = models.FileField(upload_to=upload_to, null=True)
    data_file_type = models.CharField(max_length=255, null=True)

    @property
    def hash(self):
        if self.data_file.storage.exists(self.data_file.name) \
                or self.data_file.name != '':
            self.data_file.seek(0)

            return u'%s' % md5(self.data_file.read()).hexdigest()

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
    def media_upload(xform, data_file=None):
        data_type = 'media'
        if data_file:
            if data_file.content_type in settings.SUPPORTED_MEDIA_UPLOAD_TYPES:
                media = MetaData(data_type=data_type, xform=xform,
                                 data_value=data_file.name,
                                 data_file=data_file,
                                 data_file_type=data_file.content_type)
                media.save()
        return media_resources(type_for_form(xform, data_type))

    @staticmethod
    def media_add_uri(xform, uri):
        """Add a uri as a media resource"""
        data_type = 'media'

        try:
            urlvalidate(uri)
        except ValidationError as e:
            raise e
        else:
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

    class Meta:
        app_label = 'main'
