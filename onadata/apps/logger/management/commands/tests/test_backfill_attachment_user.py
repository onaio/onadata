# -*- coding: utf-8 -*-
"""Tests for management command backfill_attachment_user."""

from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.management import call_command

from onadata.apps.logger.models import Attachment, KMSKey
from onadata.apps.main.tests.test_base import TestBase


class BackfillAttachmentUserTestCase(TestBase):
    """Tests for management command backfill_attachment_user."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form_and_submit_instance()
        self.instance = self.xform.instances.first()
        org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=ContentType.objects.get_for_model(org),
            object_id=org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        self.xform.kms_keys.create(kms_key=kms_key, version=self.xform.version)
        self.out = StringIO()

    def _create_attachment(self, name):
        return Attachment.objects.create(
            instance=self.instance,
            xform=self.xform,
            media_file=ContentFile(b"fake-media", name=name),
            mimetype="image/png",
            extension="png",
        )

    def test_backfill_attachment_user(self):
        """Command sets null attachment user from the submission's user."""
        attachment = self._create_attachment("sunset.png")
        self.assertIsNone(attachment.user)

        call_command("backfill_attachment_user", stdout=self.out)

        attachment.refresh_from_db()
        self.assertEqual(attachment.user, self.instance.user)
        self.assertIn("Updated 1 attachment(s).", self.out.getvalue())

    def test_batch_size(self):
        """Command updates attachments across multiple batches."""
        attachments = [
            self._create_attachment("sunset.png"),
            self._create_attachment("forest.mp4"),
        ]

        call_command("backfill_attachment_user", batch_size=1, stdout=self.out)

        for attachment in attachments:
            attachment.refresh_from_db()
            self.assertEqual(attachment.user, self.instance.user)
        self.assertIn("Updated 2 attachment(s).", self.out.getvalue())
