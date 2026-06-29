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
