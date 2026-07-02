"""
Tests for PendingEmailChange model and OTP helpers.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from onadata.apps.main.models import PendingEmailChange

User = get_user_model()


class PendingEmailChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="bob", email="bob@x.com")

    def test_start_generates_6_digit_and_hashes(self):
        pec, code = PendingEmailChange.start(self.user, "New@X.com")
        self.assertRegex(code, r"^\d{6}$")
        self.assertEqual(pec.new_email, "new@x.com")
        self.assertNotIn(code, pec.code_hash)
        self.assertTrue(pec.verify(code))

    def test_wrong_code_counts_attempt_and_fails(self):
        pec, _ = PendingEmailChange.start(self.user, "n@x.com")
        self.assertFalse(pec.verify("000000"))
        self.assertEqual(PendingEmailChange.objects.get(pk=pec.pk).attempts, 1)

    def test_expired_fails(self):
        pec, code = PendingEmailChange.start(self.user, "n@x.com")
        pec.expires_at = timezone.now() - timedelta(seconds=1)
        pec.save()
        self.assertFalse(pec.verify(code))

    def test_over_max_attempts_fails(self):
        pec, code = PendingEmailChange.start(self.user, "n@x.com")
        for _ in range(PendingEmailChange.MAX_ATTEMPTS):
            pec.verify("000000")
        self.assertFalse(pec.verify(code))  # correct code now rejected

    def test_hash_is_keyed_not_bare_sha256(self):
        """code_hash is a keyed HMAC, not a reversible bare SHA-256 digest."""
        import hashlib

        pec, code = PendingEmailChange.start(self.user, "n@x.com")
        self.assertNotEqual(pec.code_hash, hashlib.sha256(code.encode()).hexdigest())
        self.assertTrue(pec.verify(code))  # correct code still validates

    def test_consume_returns_email_and_retires_row(self):
        pec, code = PendingEmailChange.start(self.user, "New@X.com")
        self.assertEqual(pec.consume(code), "new@x.com")
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_consume_wrong_code_returns_none_and_keeps_row(self):
        pec, _ = PendingEmailChange.start(self.user, "n@x.com")
        self.assertIsNone(pec.consume("000000"))
        self.assertTrue(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_purge_expired_deletes_only_expired(self):
        """Abandoned/expired rows are purged; live ones are kept."""
        other = User.objects.create(username="carol", email="carol@x.com")
        PendingEmailChange.start(self.user, "live@x.com")  # live
        stale, _ = PendingEmailChange.start(other, "old@x.com")
        stale.expires_at = timezone.now() - timedelta(seconds=1)
        stale.save(update_fields=["expires_at"])

        deleted = PendingEmailChange.purge_expired()

        self.assertEqual(deleted, 1)
        self.assertTrue(PendingEmailChange.objects.filter(user=self.user).exists())
        self.assertFalse(PendingEmailChange.objects.filter(user=other).exists())
