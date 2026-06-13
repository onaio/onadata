# -*- coding: utf-8 -*-
"""Tests for management command backfill_last_edited_by."""

import os
from io import StringIO

from django.core.management import call_command

from django_digest.test import DigestAuth
from guardian.shortcuts import assign_perm

from onadata.apps.logger.models import Instance, InstanceHistory
from onadata.apps.main.tests.test_base import TestBase


class BackfillLastEditedByTestCase(TestBase):
    """Tests for management command backfill_last_edited_by."""

    def setUp(self):
        super().setUp()
        self._create_user_and_login()
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        self.out = StringIO()

    def _submission_file(self, filename):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../../fixtures/tutorial/instances",
            filename,
        )

    def test_backfill_last_edited_by_uses_latest_editor(self):
        """Command sets last_edited_by to the latest history user."""
        original_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        edited_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        second_edited_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_again.xml"
        )

        self._make_submission(original_submission)
        self.assertEqual(Instance.objects.count(), 1)
        self.assertFalse(InstanceHistory.objects.exists())

        alice = self._create_user("alice", "alice", create_profile=True)
        assign_perm("logger.change_xform", alice, self.xform)
        alice_auth = DigestAuth("alice", "alice")

        self._make_submission(edited_submission, auth=alice_auth)
        self._make_submission(second_edited_submission)

        instance = Instance.objects.get(pk=self.xform.instances.first().pk)
        self.assertEqual(instance.submission_history.count(), 2)
        self.assertEqual(InstanceHistory.objects.count(), 2)

        instance.last_edited_by = None
        instance.save(update_fields=["last_edited_by"])

        call_command("backfill_last_edited_by", stdout=self.out)

        instance.refresh_from_db()
        self.assertEqual(instance.last_edited_by, self.user)
        self.assertIn("Updated 1 last edited by value(s).", self.out.getvalue())
        self.assertIn("Processed 1 edited submission(s).", self.out.getvalue())

    def test_backfill_last_edited_by_skips_processed_rows(self):
        """Command skips submissions that already have last_edited_by set."""
        original_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )
        edited_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        second_edited_submission = self._submission_file(
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_again.xml"
        )

        self._make_submission(original_submission)
        alice = self._create_user("alice", "alice", create_profile=True)
        assign_perm("logger.change_xform", alice, self.xform)
        alice_auth = DigestAuth("alice", "alice")

        self._make_submission(edited_submission, auth=alice_auth)
        self._make_submission(second_edited_submission)

        instance = Instance.objects.get(pk=self.xform.instances.first().pk)
        instance.last_edited_by = self.user
        instance.save(update_fields=["last_edited_by"])

        self.out.truncate(0)
        self.out.seek(0)
        call_command("backfill_last_edited_by", stdout=self.out)

        instance.refresh_from_db()
        self.assertEqual(instance.last_edited_by, self.user)
        self.assertIn("Processed 0 edited submission(s).", self.out.getvalue())
        self.assertIn("Updated 0 last edited by value(s).", self.out.getvalue())
