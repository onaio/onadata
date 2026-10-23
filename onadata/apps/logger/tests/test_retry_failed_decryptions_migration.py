"""Tests for the logger.0049_retry_failed_decryptions migration."""

from importlib import import_module

from django.apps import apps

from onadata.apps.logger.models import Instance
from onadata.apps.main.tests.test_base import TestBase

migration = import_module(
    "onadata.apps.logger.migrations.0049_retry_failed_decryptions"
)


class RetryFailedDecryptionsTestCase(TestBase):
    """Tests for retry_failed_decryptions."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self._make_submissions()
        self.instances = list(self.xform.instances.order_by("pk"))

    def _set_decryption_error(self, instance, error_name):
        Instance.objects.filter(pk=instance.pk).update(
            is_encrypted=True,
            decryption_status=Instance.DecryptionStatus.FAILED,
            json={**instance.json, "_decryption_error": error_name},
        )

    def test_retry_failed_decryptions(self):
        """Submissions that failed for a temporary reason are pending again."""
        self._set_decryption_error(self.instances[0], "NOT_ALL_MEDIA_RECEIVED")
        self._set_decryption_error(self.instances[1], "MAX_RETRIES_EXCEEDED")
        self._set_decryption_error(self.instances[2], "KMS_KEY_DISABLED")

        migration.retry_failed_decryptions(apps, None)

        statuses = [
            (i.decryption_status, i.json.get("_decryption_error"))
            for i in Instance.objects.filter(
                pk__in=[i.pk for i in self.instances[:3]]
            ).order_by("pk")
        ]
        self.assertEqual(
            statuses,
            [
                (Instance.DecryptionStatus.PENDING, "NOT_ALL_MEDIA_RECEIVED"),
                (Instance.DecryptionStatus.PENDING, "MAX_RETRIES_EXCEEDED"),
                (Instance.DecryptionStatus.FAILED, "KMS_KEY_DISABLED"),
            ],
        )
