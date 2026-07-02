# -*- coding: utf-8 -*-
"""
Test purge_expired_email_changes management command.
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from onadata.apps.main.models import PendingEmailChange

User = get_user_model()


class TestPurgeExpiredEmailChangesCommand(TestCase):
    """Test the purge_expired_email_changes command."""

    def setUp(self):
        self.user = User.objects.create(username="bob", email="bob@x.com")
        pec, _ = PendingEmailChange.start(self.user, "new@x.com")
        pec.expires_at = timezone.now() - timedelta(seconds=1)
        pec.save(update_fields=["expires_at"])

    def test_deletes_expired(self):
        """The command removes expired rows."""
        call_command("purge_expired_email_changes")
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_dry_run_reports_without_deleting(self):
        """--dry-run reports the count and leaves the rows in place."""
        out = StringIO()
        call_command("purge_expired_email_changes", "--dry-run", stdout=out)
        self.assertTrue(PendingEmailChange.objects.filter(user=self.user).exists())
        self.assertIn("Would delete 1", out.getvalue())
