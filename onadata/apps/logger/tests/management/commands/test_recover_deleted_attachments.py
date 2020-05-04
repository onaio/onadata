"""
Module containing the tests for the recover_deleted_attachments
management command
"""
from io import BytesIO
from datetime import datetime

from django.conf import settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.import_tools import django_file
from onadata.apps.logger.management.commands.recover_deleted_attachments \
    import recover_deleted_attachments
from onadata.libs.utils.logger_tools import create_instance


class TestRecoverDeletedAttachments(TestBase):
    """TestRecoverDeletedAttachments Class"""
    # pylint: disable=invalid-name
    def test_recovers_wrongly_deleted_attachments(self):
        """
        Test that the command recovers the correct
        attachment
        """
        md = """
        | survey |       |        |       |
        |        | type  | name   | label |
        |        | file  | file   | File  |
        |        | image | image  | Image |
        """  # pylint: disable=invalid-name
        self._create_user_and_login()
        xform = self._publish_markdown(md, self.user)

        xml_string = f"""
        <data id="{xform.id_string}">
            <meta>
                <instanceID>uuid:UJ5jz4EszdgH8uhy8nss1AsKaqBPO5VN7</instanceID>
            </meta>
            <file>Health_2011_03_13.xml_2011-03-15_20-30-28.xml</file>
            <image>1300221157303.jpg</image>
        </data>
        """
        media_root = (f'{settings.PROJECT_ROOT}/apps/logger/tests/Health'
                      '_2011_03_13.xml_2011-03-15_20-30-28/')
        image_media = django_file(
            path=f'{media_root}1300221157303.jpg', field_name='image',
            content_type='image/jpeg')
        file_media = django_file(
            path=f'{media_root}Health_2011_03_13.xml_2011-03-15_20-30-28.xml',
            field_name='file', content_type='text/xml')
        instance = create_instance(
            self.user.username,
            BytesIO(xml_string.strip().encode('utf-8')),
            media_files=[file_media, image_media])
        self.assertEqual(
            instance.attachments.filter(deleted_at__isnull=True).count(), 2)
        attachment = instance.attachments.first()

        # Soft delete attachment
        attachment.deleted_at = datetime.now()
        attachment.deleted_by = self.user
        attachment.save()

        self.assertEqual(
            instance.attachments.filter(deleted_at__isnull=True).count(), 1)

        # Attempt recovery of attachment
        recover_deleted_attachments(form_id=instance.xform.id)

        self.assertEqual(
            instance.attachments.filter(deleted_at__isnull=True).count(), 2)
        attachment.refresh_from_db()
        self.assertIsNone(attachment.deleted_at)
        self.assertIsNone(attachment.deleted_by)
