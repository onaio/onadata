from datetime import datetime
import os

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.management import call_command

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Attachment, Instance
from onadata.libs.utils.image_tools import image_url


class TestAttachment(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_transportation_form_and_submit_instance()
        self.media_file = "1335783522563.jpg"
        media_file = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', self.surveys[0], self.media_file)
        self.instance = Instance.objects.all()[0]
        self.attachment = Attachment.objects.create(
            instance=self.instance,
            media_file=File(open(media_file), media_file))

    def test_mimetype(self):
        self.assertEqual(self.attachment.mimetype, 'image/jpeg')

    def test_create_attachment_with_media_file_length_more_the_100(self):
        with self.assertRaises(ValueError):
            Attachment.objects.create(
                instance=self.instance,
                media_file='a'*300
            )

        pre_count = Attachment.objects.count()
        Attachment.objects.create(
            instance=self.instance,
            media_file='a'*150
        )
        self.assertEqual(pre_count + 1, Attachment.objects.count())

    def test_thumbnails(self):
        for attachment in Attachment.objects.filter(instance=self.instance):
            url = image_url(attachment, 'small')
            filename = attachment.media_file.name.replace('.jpg', '')
            thumbnail = '%s-small.jpg' % filename
            self.assertNotEqual(
                url.find(thumbnail), -1)
            for size in ['small', 'medium', 'large']:
                thumbnail = '%s-%s.jpg' % (filename, size)
                self.assertTrue(
                    default_storage.exists(thumbnail))
                default_storage.delete(thumbnail)

    def test_create_thumbnails_command(self):
        call_command("create_image_thumbnails")
        for attachment in Attachment.objects.filter(instance=self.instance):
            filename = attachment.media_file.name.replace('.jpg', '')
            for size in ['small', 'medium', 'large']:
                thumbnail = '%s-%s.jpg' % (filename, size)
                self.assertTrue(
                    default_storage.exists(thumbnail))
        check_datetime = datetime.now()
        # replace or regenerate thumbnails if they exist
        call_command("create_image_thumbnails", force=True)
        for attachment in Attachment.objects.filter(instance=self.instance):
            filename = attachment.media_file.name.replace('.jpg', '')
            for size in ['small', 'medium', 'large']:
                thumbnail = '%s-%s.jpg' % (filename, size)
                self.assertTrue(
                    default_storage.exists(thumbnail))
                self.assertTrue(
                    default_storage.modified_time(thumbnail) > check_datetime)
                default_storage.delete(thumbnail)
