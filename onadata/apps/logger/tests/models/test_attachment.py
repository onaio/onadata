import os
from datetime import datetime
from builtins import open

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.db.utils import DataError
from django.utils import timezone

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Attachment, Instance
from onadata.apps.logger.models.attachment import (get_original_filename,
                                                   upload_to)
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
            media_file=File(open(media_file, 'rb'), media_file))

    def test_mimetype(self):
        self.assertEqual(self.attachment.mimetype, 'image/jpeg')

    def test_create_attachment_with_mimetype_more_than_50(self):
        media_file = os.path.join(
            self.this_directory, 'fixtures',
            'transportation', 'instances', self.surveys[0], self.media_file)
        media_file = File(open(media_file, 'rb'), media_file)
        with self.assertRaises(DataError):
            Attachment.objects.create(
                instance=self.instance,
                mimetype='a'*120,
                media_file=media_file
            )

        pre_count = Attachment.objects.count()
        Attachment.objects.create(
            instance=self.instance,
            mimetype='a'*100,
            media_file=media_file
        )
        self.assertEqual(pre_count + 1, Attachment.objects.count())

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
        check_datetime = timezone.now()
        # replace or regenerate thumbnails if they exist
        call_command("create_image_thumbnails", force=True)
        for attachment in Attachment.objects.filter(instance=self.instance):
            filename = attachment.media_file.name.replace('.jpg', '')
            for size in ['small', 'medium', 'large']:
                thumbnail = '%s-%s.jpg' % (filename, size)
                self.assertTrue(
                    default_storage.exists(thumbnail))

                self.assertTrue(
                    default_storage.get_modified_time(thumbnail) >
                check_datetime)
                default_storage.delete(thumbnail)

    def test_get_original_filename(self):
        self.assertEqual(
            get_original_filename('submission.xml_K337n8u.enc'),
            'submission.xml.enc'
        )
        self.assertEqual(
            get_original_filename('submission.xml.enc'),
            'submission.xml.enc'
        )
        self.assertEqual(
            get_original_filename('submission_test.xml_K337n8u.enc'),
            'submission_test.xml.enc'
        )
        self.assertEqual(
            get_original_filename('submission_random.enc'),
            'submission_random.enc'
        )

    def test_upload_to(self):
        """
        Test that upload to returns the correct path
        """
        path = upload_to(self.attachment, self.attachment.filename)
        self.assertEqual(path,
                         'bob/attachments/{}_{}/1335783522563.jpg'.format(
                             self.xform.id, self.xform.id_string))
