import os
import mimetypes

from hashlib import md5
from django.db import models

from instance import Instance


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
        max_length=50, null=False, blank=True, default='')
    extension = models.CharField(max_length=10, null=False, blank=False,
                                 default=u"non", db_index=True)

    class Meta:
        app_label = 'logger'

    def save(self, *args, **kwargs):
        if self.media_file and self.mimetype == '':
            # guess mimetype
            mimetype, encoding = mimetypes.guess_type(self.media_file.name)
            if mimetype:
                self.mimetype = mimetype
        if len(self.media_file.name) > 255:
            raise ValueError(
                "Length of the media file should be less or equal to 255")

        super(Attachment, self).save(*args, **kwargs)

    @property
    def file_hash(self):
        if self.media_file.storage.exists(self.media_file.name):
            return u'%s' % md5(self.media_file.read()).hexdigest()
        return u''

    @property
    def filename(self):
        return os.path.basename(self.media_file.name)
