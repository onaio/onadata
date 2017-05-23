import os
import mimetypes

from hashlib import md5
from django.db import models

from instance import Instance


def get_original_filename(filename):
    # https://docs.djangoproject.com/en/1.8/ref/files/storage/
    # #django.core.files.storage.Storage.get_available_name
    # If a file with name already exists, an underscore plus a random
    # 7 character alphanumeric string is appended to the filename
    # before the extension.
    # this code trys to reverse this effect to derive the original name
    if filename:
        parts = filename.split('_')
        if len(parts) > 1:
            ext_parts = parts[-1].split('.')
            if len(ext_parts[0]) == 7 and len(ext_parts) == 2:
                ext = ext_parts[1]

                return u'.'.join([u'_'.join(parts[:-1]), ext])

    return filename


def upload_to(instance, filename):
    return os.path.join(
        instance.instance.xform.user.username,
        'attachments',
        os.path.split(filename)[1])


class Attachment(models.Model):
    OSM = 'osm'
    instance = models.ForeignKey(Instance, related_name="attachments")
    media_file = models.FileField(max_length=255, upload_to=upload_to)
    mimetype = models.CharField(
        max_length=100, null=False, blank=True, default='')
    extension = models.CharField(max_length=10, null=False, blank=False,
                                 default=u"non", db_index=True)
    date_created = models.DateTimeField(null=True, auto_now_add=True)
    date_modified = models.DateTimeField(null=True, auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)
    file_size = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'logger'
        ordering = ("pk", )

    def save(self, *args, **kwargs):
        if self.media_file and self.mimetype == '':
            # guess mimetype
            mimetype, encoding = mimetypes.guess_type(self.media_file.name)
            if mimetype:
                self.mimetype = mimetype
        if self.media_file and len(self.media_file.name) > 255:
            raise ValueError(
                "Length of the media file should be less or equal to 255")

        try:
            f_size = self.media_file.size
            if f_size:
                self.file_size = f_size
        except (OSError, AttributeError):
            pass

        super(Attachment, self).save(*args, **kwargs)

    @property
    def file_hash(self):
        if self.media_file.storage.exists(self.media_file.name):
            return u'%s' % md5(self.media_file.read()).hexdigest()
        return u''

    @property
    def filename(self):
        if self.media_file:
            return os.path.basename(self.media_file.name)

    @property
    def name(self):
        return get_original_filename(self.filename)
