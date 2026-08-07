# -*- coding: utf-8 -*-
"""Tests for logger data migrations."""

import base64
from hashlib import sha256
from importlib import import_module
from io import BytesIO
from unittest.mock import patch

from django.apps import apps
from django.core.files.base import File
from django.test import override_settings
from django.utils import timezone

from moto import mock_aws

from onadata.apps.logger.models import Attachment, Instance, SurveyType
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.kms.tools import create_key

migration = import_module(
    "onadata.apps.logger.migrations.0042_decrypt_swept_encrypted_submissions"
)


@mock_aws
@override_settings(
    KMS_PROVIDER="AWS",
    AWS_ACCESS_KEY_ID="fake-id",
    AWS_SECRET_ACCESS_KEY="fake-secret",
    AWS_KMS_REGION_NAME="us-east-1",
)
class DecryptSweptEncryptedSubmissionsTestCase(TestBase):
    """Tests for `decrypt_swept_encrypted_submissions`"""

    def setUp(self):
        super().setUp()

        self.instance_version = "202502131337"
        self.instance_uuid = "uuid:a10ead67-7415-47da-b823-0947ab8a8ef0"
        self.form_id = "test_valigetta"

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.dec_submission_xml = f"""
        <data xmlns:jr="http://openrosa.org/javarosa" xmlns:orx="http://openrosa.org/xforms"
            id="{self.form_id}" version="{self.instance_version}">
            <formhub>
                <uuid>76972fb82e41400c840019938b188ce8</uuid>
            </formhub>
            <sunset>sunset.png</sunset>
            <forest>forest.mp4</forest>
            <meta>
                <instanceID>{self.instance_uuid}</instanceID>
            </meta>
        </data>
        """.strip()
        self.dec_submission_file = BytesIO(self.dec_submission_xml.encode("utf-8"))
        self.dec_media = {
            "sunset.png": BytesIO(b"Fake PNG image data"),
            "forest.mp4": BytesIO(b"Fake MP4 video data"),
        }
        dec_aes_key = b"0123456789abcdef0123456789abcdef"
        self.kms_key = create_key(self.org)
        enc_aes_key = self._kms_encrypt(
            key_id=self.kms_key.key_id, plain_text=dec_aes_key
        )
        enc_signature = self._create_encrypted_signature(
            key_id=self.kms_key.key_id,
            form_id=self.form_id,
            version=self.instance_version,
            enc_aes_key=enc_aes_key,
            instance_uuid=self.instance_uuid,
            dec_submission=self.dec_submission_file,
            dec_media=self.dec_media,
        )
        enc_key_b64 = base64.b64encode(enc_aes_key).decode("utf-8")
        enc_signature_b64 = base64.b64encode(enc_signature).decode("utf-8")

        self.metadata_xml = self._create_encrypted_submission_manifest(
            form_id=self.form_id,
            version=self.instance_version,
            enc_key_b64=enc_key_b64,
            instance_uuid=self.instance_uuid,
            enc_signature_b64=enc_signature_b64,
            media_files=["sunset.png.enc", "forest.mp4.enc"],
        )
        self.metadata_xml_file = BytesIO(self.metadata_xml.encode("utf-8"))

        md = """
        | survey  |
        |         | type  | name   | label                |
        |         | photo | sunset | Take photo of sunset |
        |         | video | forest | Take a video of forest|
        """
        self.xform = self._publish_markdown(md, self.user, id_string="nature")
        self.xform.is_managed = True
        self.xform.save(update_fields=["is_managed"])
        survey_type = SurveyType.objects.create(slug="slug-foo")
        self.instance = Instance.objects.create(
            xform=self.xform,
            xml=self.metadata_xml,
            user=self.user,
            survey_type=survey_type,
            checksum=sha256(self.metadata_xml_file.getvalue()).hexdigest(),
        )
        self.instance.refresh_from_db()
        dec_files = [
            ("sunset.png", self.dec_media["sunset.png"]),
            ("forest.mp4", self.dec_media["forest.mp4"]),
            ("submission.xml", self.dec_submission_file),
        ]
        attachments = []

        for index, (name, file) in enumerate(dec_files, start=1):
            enc_file_name = f"{name}.enc"
            enc_file = self._encrypt_submission_file(
                dec_aes_key, self.instance_uuid, index, file.getvalue()
            )
            attachment = Attachment(
                instance=self.instance,
                xform=self.xform,
                media_file=File(enc_file, name=enc_file_name),
                mimetype="application/octet-stream",
                extension="enc",
                file_size=len(file.getbuffer()),
                name=enc_file_name,
            )
            attachments.append(attachment)

        Attachment.objects.bulk_create(attachments)

        self.xform.kms_keys.create(version=self.instance_version, kms_key=self.kms_key)

    @patch(
        "onadata.apps.logger.tasks.adjust_xform_num_of_decrypted_submissions_async.delay"
    )
    def test_swept_submission_decrypted(self, mock_adjust_decrypted_submission_count):
        """A submission whose ciphertext was swept is restored and decrypted."""
        # Simulate the sweep: ciphertext soft-deleted by the system, no user
        self.instance.attachments.update(deleted_at=timezone.now())
        Instance.objects.filter(pk=self.instance.pk).update(
            decryption_status=Instance.DecryptionStatus.FAILED
        )

        migration.decrypt_swept_encrypted_submissions(apps, None)

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.xml, self.dec_submission_xml)
        self.assertFalse(self.instance.is_encrypted)
        self.assertEqual(
            self.instance.decryption_status, Instance.DecryptionStatus.SUCCESS
        )
        self.assertCountEqual(
            self.instance.attachments.filter(deleted_at__isnull=True).values_list(
                "name", flat=True
            ),
            ["sunset.png", "forest.mp4"],
        )
