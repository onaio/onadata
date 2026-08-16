"""Tests for the fix_submission_count management command."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.cache_tools import (
    XFORM_COUNT,
    safe_cache_get,
    safe_cache_set,
)


class FixSubmissionCountTestCase(TestBase):
    """Test submission count reporting and repair."""

    def _create_corrupt_counts(self):
        merged_xform = self._create_merged_dataset(make_submissions=True)
        xform_a = XForm.objects.get(id_string="a")
        xform_b = XForm.objects.get(id_string="b")

        instance_b = xform_b.instances.get()
        instance_b.deleted_at = timezone.now()
        instance_b.save()

        XForm.objects.filter(pk=xform_a.pk).update(num_of_submissions=10)
        XForm.objects.filter(pk=xform_b.pk).update(num_of_submissions=11)
        XForm.objects.filter(pk=merged_xform.pk).update(num_of_submissions=12)
        self.user.profile.num_of_submissions = 13
        self.user.profile.save(update_fields=["num_of_submissions"])

        safe_cache_set(f"{XFORM_COUNT}{xform_a.pk}", 10)
        safe_cache_set(f"{XFORM_COUNT}{xform_b.pk}", 11)
        safe_cache_set(f"{XFORM_COUNT}{merged_xform.pk}", 12)

        return xform_a, xform_b, merged_xform

    @patch(
        "onadata.apps.logger.management.commands.fix_submission_count."
        "clear_project_cache"
    )
    def test_dry_run_reports_without_updating(self, clear_project_cache):
        """Dry run reports every mismatch without changing data or caches."""
        xform_a, xform_b, merged_xform = self._create_corrupt_counts()
        output = StringIO()

        call_command("fix_submission_count", dry_run=True, stdout=output)

        xform_a.refresh_from_db()
        xform_b.refresh_from_db()
        merged_xform.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(xform_a.num_of_submissions, 10)
        self.assertEqual(xform_b.num_of_submissions, 11)
        self.assertEqual(merged_xform.num_of_submissions, 12)
        self.assertEqual(self.user.profile.num_of_submissions, 13)
        self.assertEqual(safe_cache_get(f"{XFORM_COUNT}{xform_a.pk}"), 10)
        self.assertFalse(clear_project_cache.called)
        self.assertIn(
            "Found 3 form count mismatch(es) and 1 profile count mismatch(es).",
            output.getvalue(),
        )

    @patch(
        "onadata.apps.logger.management.commands.fix_submission_count."
        "clear_project_cache"
    )
    def test_repairs_counts_and_invalidates_caches(self, clear_project_cache):
        """Repair uses active rows and refreshes merged and cached counts."""
        xform_a, xform_b, merged_xform = self._create_corrupt_counts()
        output = StringIO()

        call_command("fix_submission_count", stdout=output)

        xform_a.refresh_from_db()
        xform_b.refresh_from_db()
        merged_xform.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(xform_a.num_of_submissions, 1)
        self.assertEqual(xform_b.num_of_submissions, 0)
        self.assertEqual(merged_xform.num_of_submissions, 1)
        self.assertEqual(self.user.profile.num_of_submissions, 1)
        self.assertIsNone(safe_cache_get(f"{XFORM_COUNT}{xform_a.pk}"))
        self.assertIsNone(safe_cache_get(f"{XFORM_COUNT}{xform_b.pk}"))
        self.assertIsNone(safe_cache_get(f"{XFORM_COUNT}{merged_xform.pk}"))
        clear_project_cache.assert_called_once_with(self.project.pk)
        self.assertIn(
            "Repaired 3 form count mismatch(es) and 1 profile count mismatch(es).",
            output.getvalue(),
        )
