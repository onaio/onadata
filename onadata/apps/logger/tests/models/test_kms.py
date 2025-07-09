"""
Tests for module onadata.apps.logger.models.kms
"""

from datetime import datetime, timedelta
from datetime import timezone as tz
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.db import DataError, IntegrityError
from django.utils import timezone

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models.kms import KMSKey, XFormKey
from onadata.apps.main.tests.test_base import TestBase


class KMSKeyTestCase(TestBase):
    """Tests for model KMSKey."""

    def setUp(self):
        super().setUp()

        self.mocked_now = datetime(2025, 4, 1, tzinfo=tz.utc)
        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(OrganizationProfile)

    @patch("django.utils.timezone.now")
    def test_creation(self, mock_now):
        """We can create a KMSKey."""
        mock_now.return_value = self.mocked_now
        expiry_date = self.mocked_now + timedelta(days=2)
        grace_end_date = self.mocked_now + timedelta(days=1)
        disabled_at = self.mocked_now
        rotated_at = self.mocked_now
        rotation_reason = "Test rotation"

        kms_key = KMSKey.objects.create(
            key_id="1234",
            description="Key-2025-04-01",
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            expiry_date=expiry_date,
            grace_end_date=grace_end_date,
            disabled_at=disabled_at,
            content_type=self.content_type,
            object_id=self.org.id,
            disabled_by=self.user,
            created_by=self.user,
            rotated_at=rotated_at,
            rotated_by=self.user,
            rotation_reason=rotation_reason,
            is_active=True,
        )

        self.assertEqual(f"{kms_key}", "1234")
        self.assertEqual(kms_key.key_id, "1234")
        self.assertEqual(kms_key.description, "Key-2025-04-01")
        self.assertEqual(kms_key.provider, KMSKey.KMSProvider.AWS)
        self.assertEqual(kms_key.expiry_date, expiry_date)
        self.assertEqual(kms_key.disabled_at, disabled_at)
        self.assertEqual(kms_key.object_id, self.org.id)
        self.assertEqual(kms_key.content_type, self.content_type)
        self.assertEqual(kms_key.disabled_by, self.user)
        self.assertEqual(kms_key.created_by, self.user)
        self.assertEqual(kms_key.grace_end_date, grace_end_date)
        self.assertEqual(kms_key.rotated_at, rotated_at)
        self.assertEqual(kms_key.rotated_by, self.user)
        self.assertEqual(kms_key.rotation_reason, rotation_reason)
        self.assertTrue(kms_key.is_active)

    def test_default_values(self):
        """Default values for optional fields are correct."""
        kms_key = KMSKey.objects.create(
            key_id="1234",
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        self.assertIsNone(kms_key.description)
        self.assertIsNone(kms_key.expiry_date)
        self.assertIsNone(kms_key.disabled_at)
        self.assertIsNone(kms_key.disabled_by)
        self.assertIsNone(kms_key.created_by)
        self.assertIsNone(kms_key.grace_end_date)
        self.assertIsNone(kms_key.rotated_at)
        self.assertIsNone(kms_key.rotated_by)
        self.assertIsNone(kms_key.rotation_reason)
        self.assertTrue(kms_key.is_active)

    def test_key_id_provider_unique(self):
        """key_id, provider are unique together."""
        KMSKey.objects.create(
            key_id="1234",
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        # Duplicate not allowed
        with self.assertRaises(IntegrityError):
            KMSKey.objects.create(
                key_id="1234",
                public_key="fake-pub-key",
                provider=KMSKey.KMSProvider.AWS,
                content_type=self.content_type,
                object_id=self.org.id,
            )

    def test_key_id_max_length(self):
        """key_id maximum length is 255."""
        key_id = "1" * 256

        # 256 characters fails
        self.assertEqual(len(key_id), 256)

        with self.assertRaises(DataError):
            KMSKey.objects.create(
                key_id=key_id,
                public_key="fake-pub-key",
                provider=KMSKey.KMSProvider.AWS,
                content_type=self.content_type,
                object_id=self.org.id,
            )

        # 255 characters succeeds
        key_id = key_id[:-1]

        kms_key = KMSKey.objects.create(
            key_id=key_id,
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        self.assertEqual(len(kms_key.key_id), 255)

    def test_description_max_length(self):
        """description maximum length is 255."""
        desc = "1" * 256

        # 256 characters fails
        self.assertEqual(len(desc), 256)

        with self.assertRaises(DataError):
            KMSKey.objects.create(
                key_id="1234",
                description=desc,
                public_key="fake-pub-key",
                provider=KMSKey.KMSProvider.AWS,
                content_type=self.content_type,
                object_id=self.org.id,
            )

        # 255 characters succeeds
        desc = desc[:-1]

        kms_key = KMSKey.objects.create(
            key_id="1234",
            description=desc,
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        self.assertEqual(len(kms_key.description), 255)

    def test_rotation_reason_max_length(self):
        """rotation_reason maximum length is 255."""
        rotation_reason = "1" * 256

        # 256 characters fails
        self.assertEqual(len(rotation_reason), 256)

        with self.assertRaises(DataError):
            KMSKey.objects.create(
                key_id="1234",
                rotation_reason=rotation_reason,
                provider=KMSKey.KMSProvider.AWS,
                content_type=self.content_type,
                object_id=self.org.id,
            )

        # 255 characters succeeds
        rotation_reason = rotation_reason[:-1]

        kms_key = KMSKey.objects.create(
            key_id="1234",
            rotation_reason=rotation_reason,
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        self.assertEqual(len(kms_key.rotation_reason), 255)

    def test_is_expired(self):
        """is_expired property works"""
        kms_key = KMSKey.objects.create(
            key_id="1234",
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )

        # expiry_date is None
        self.assertFalse(kms_key.is_expired)

        # expiry_date is in the past
        kms_key.expiry_date = timezone.now() - timedelta(days=1)
        kms_key.save()
        kms_key.refresh_from_db()

        self.assertTrue(kms_key.is_expired)

        # expiry_date is in the future
        kms_key.expiry_date = timezone.now() + timedelta(days=1)
        kms_key.save()
        kms_key.refresh_from_db()

        self.assertFalse(kms_key.is_expired)


class XFormKeyTestCase(TestBase):
    """Tests for model XFormKey."""

    def setUp(self):
        super().setUp()

        self.org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.content_type = ContentType.objects.get_for_model(OrganizationProfile)
        self.kms_key = KMSKey.objects.create(
            key_id="1234",
            public_key="fake-pub-key",
            provider=KMSKey.KMSProvider.AWS,
            content_type=self.content_type,
            object_id=self.org.id,
        )
        self._publish_transportation_form()
        self.version = "202502131337"

    def test_creation(self):
        """We can created XFormKey."""
        xform_key = XFormKey.objects.create(
            xform=self.xform,
            kms_key=self.kms_key,
            version=self.version,
            encrypted_by=self.user,
        )

        self.assertEqual(xform_key.kms_key, self.kms_key)
        self.assertEqual(xform_key.xform, self.xform)
        self.assertEqual(xform_key.version, self.version)
        self.assertEqual(xform_key.encrypted_by, self.user)

    def test_xform_kms_key_version_unique(self):
        """xform, kms_key and version are unique together."""
        XFormKey.objects.create(
            xform=self.xform, kms_key=self.kms_key, version=self.version
        )

        # Duplicate
        with self.assertRaises(IntegrityError):
            XFormKey.objects.create(
                xform=self.xform, kms_key=self.kms_key, version=self.version
            )

    def test_related_names(self):
        """Related names are set."""
        XFormKey.objects.create(
            xform=self.xform, kms_key=self.kms_key, version=self.version
        )

        self.assertEqual(self.kms_key.xforms.all().count(), 1)
        self.assertEqual(self.xform.kms_keys.all().count(), 1)

    def test_defaults(self):
        """Default values for optional fields are correct."""
        xform_key = XFormKey.objects.create(
            xform=self.xform,
            kms_key=self.kms_key,
            version=self.version,
        )

        self.assertIsNone(xform_key.encrypted_by)
