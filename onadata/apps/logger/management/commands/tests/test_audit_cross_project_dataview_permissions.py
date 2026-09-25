"""Tests for the cross-project DataView permission audit command."""

import csv
import os
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

from guardian.shortcuts import assign_perm, get_perms

from onadata.apps.api.models import Team
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import (
    XForm,
    XFormGroupObjectPermission,
    XFormUserObjectPermission,
)
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ManagerRole


class AuditCrossProjectDataViewPermissionsTestCase(TestBase):
    """Exercise reporting and reviewed direct revocation."""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self.destination_project = self.project
        self.source_xform = self.xform
        self.foreign_project = Project.objects.create(
            name="Foreign project",
            organization=self.user,
            created_by=self.user,
            metadata={},
        )
        self.foreign_xform = XForm.objects.create(
            xml=self.source_xform.xml,
            json=self.source_xform.json,
            user=self.user,
            project=self.foreign_project,
        )

    def _create_cross_project_dataview(
        self, name="Cross-project DataView", deleted=False
    ):
        dataview = DataView.objects.create(
            name=name,
            xform=self.foreign_xform,
            project=self.destination_project,
            columns=[],
            query=[],
            matches_parent=True,
        )
        if deleted:
            dataview.soft_delete()
            dataview.refresh_from_db()
        return dataview

    def _assign_candidates(self):
        self.alice = self._create_user("alice", "alice")
        self.team = Team.objects.create(name="repair-reviewers", organization=self.user)
        for principal in (self.alice, self.team):
            ManagerRole.add(principal, self.destination_project)
            ManagerRole.add(principal, self.foreign_xform)

    def _report(self):
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "audit_cross_project_dataview_permissions",
            stdout=stdout,
            stderr=stderr,
        )
        reader = csv.DictReader(StringIO(stdout.getvalue()))
        return stdout.getvalue(), stderr.getvalue(), reader.fieldnames, list(reader)

    @staticmethod
    def _write_review(path, fieldnames, rows):
        with open(path, "w", encoding="utf-8", newline="") as review_file:
            writer = csv.DictWriter(review_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_dry_run_reports_cross_project_rows_and_deduplicated_candidates(self):
        """Dry-run includes deleted rows and leaves data, grants, and caches alone."""
        active = self._create_cross_project_dataview()
        deleted = self._create_cross_project_dataview(
            "Deleted cross-project DataView", deleted=True
        )
        valid = DataView.objects.create(
            name="Valid DataView",
            xform=self.source_xform,
            project=self.destination_project,
            columns=[],
            query=[],
        )
        self._assign_candidates()
        original_permissions = set(get_perms(self.alice, self.foreign_xform))

        with patch.object(DataView, "soft_delete") as soft_delete, patch(
            "onadata.apps.logger.management.commands."
            "audit_cross_project_dataview_permissions.clear_permissions_cache"
        ) as clear_permissions:
            csv_output, summary, _, rows = self._report()

        soft_delete.assert_not_called()
        clear_permissions.assert_not_called()
        active.refresh_from_db()
        deleted.refresh_from_db()
        valid.refresh_from_db()
        self.assertIsNone(active.deleted_at)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertIsNone(valid.deleted_at)
        self.assertEqual(
            set(get_perms(self.alice, self.foreign_xform)), original_permissions
        )

        dataview_rows = [row for row in rows if row["record_type"] == "dataview"]
        candidate_rows = [row for row in rows if row["record_type"] == "candidate"]
        self.assertEqual(
            [int(row["dataview_id"]) for row in dataview_rows],
            [active.pk, deleted.pk],
        )
        self.assertEqual(len(candidate_rows), 2)
        expected_dataview_ids = f"{active.pk};{deleted.pk}"
        self.assertTrue(
            all(row["dataview_ids"] == expected_dataview_ids for row in candidate_rows)
        )
        self.assertIn("cross_project_dataviews_found=2", summary)
        self.assertIn("candidates_reported=2", summary)

        with TemporaryDirectory() as directory:
            output_path = os.path.join(directory, "report.csv")
            file_summary = StringIO()
            call_command(
                "audit_cross_project_dataview_permissions",
                output=output_path,
                stdout=file_summary,
            )
            with open(output_path, encoding="utf-8") as report_file:
                self.assertEqual(report_file.read(), csv_output)
            self.assertIn("cross_project_dataviews_found=2", file_summary.getvalue())

    def test_apply_without_review_never_quarantines_dataviews(self):
        """Cross-project DataViews remain valid in both active/deleted states."""
        active = self._create_cross_project_dataview()
        deleted = self._create_cross_project_dataview(
            "Deleted cross-project DataView", deleted=True
        )
        valid = DataView.objects.create(
            name="Valid DataView",
            xform=self.source_xform,
            project=self.destination_project,
            columns=[],
            query=[],
        )
        deleted_name = deleted.name
        call_command(
            "audit_cross_project_dataview_permissions",
            apply=True,
            output="-",
            stdout=StringIO(),
            stderr=StringIO(),
        )

        active.refresh_from_db()
        deleted.refresh_from_db()
        valid.refresh_from_db()
        self.assertIsNone(active.deleted_at)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.name, deleted_name)
        self.assertIsNone(valid.deleted_at)

    def test_reviewed_revocation_removes_only_approved_direct_grant(self):
        """An approved user row preserves group and destination-project grants."""
        dataview = self._create_cross_project_dataview()
        self._assign_candidates()
        _, _, fieldnames, rows = self._report()
        approved = [
            row
            for row in rows
            if row["record_type"] == "candidate" and row["principal_type"] == "user"
        ]

        with TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "approved.csv")
            self._write_review(review_path, fieldnames, approved)
            call_command(
                "audit_cross_project_dataview_permissions",
                apply=True,
                reviewed_revocations=review_path,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        dataview.refresh_from_db()
        self.assertIsNone(dataview.deleted_at)
        self.assertFalse(
            XFormUserObjectPermission.objects.filter(
                content_object=self.foreign_xform, user=self.alice
            ).exists()
        )
        self.assertTrue(
            XFormGroupObjectPermission.objects.filter(
                content_object=self.foreign_xform, group=self.team
            ).exists()
        )
        self.assertEqual(
            set(get_perms(self.alice, self.destination_project)),
            set(ManagerRole.class_to_permissions[Project]),
        )

        second_summary = StringIO()
        with TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "approved.csv")
            self._write_review(review_path, fieldnames, approved)
            call_command(
                "audit_cross_project_dataview_permissions",
                apply=True,
                reviewed_revocations=review_path,
                output="-",
                stdout=StringIO(),
                stderr=second_summary,
            )
        self.assertIn("grants_revoked=0", second_summary.getvalue())
        self.assertIn("rows_skipped=1", second_summary.getvalue())

    def test_invalid_reviews_abort_all_mutations(self):
        """Malformed, stale, or drifted reviews cannot partially apply."""
        dataview = self._create_cross_project_dataview()
        self._assign_candidates()
        _, _, fieldnames, rows = self._report()
        approved = [row for row in rows if row["record_type"] == "candidate"]

        with TemporaryDirectory() as directory:
            review_path = os.path.join(directory, "approved.csv")
            with self.assertRaisesMessage(
                CommandError, "--reviewed-revocations requires --apply"
            ):
                call_command(
                    "audit_cross_project_dataview_permissions",
                    reviewed_revocations=review_path,
                )

            malformed = dict(approved[0])
            malformed["destination_project_id"] = "not-an-id"
            self._write_review(review_path, fieldnames, [malformed])
            with self.assertRaisesMessage(
                CommandError, "invalid destination_project_id"
            ):
                call_command(
                    "audit_cross_project_dataview_permissions",
                    apply=True,
                    reviewed_revocations=review_path,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

            user_approval = [row for row in approved if row["principal_type"] == "user"]
            self._write_review(review_path, fieldnames, user_approval)
            dataview.project = self.foreign_project
            dataview.save(update_fields=["project", "date_modified"])
            with self.assertRaisesMessage(CommandError, "DataView relationship"):
                call_command(
                    "audit_cross_project_dataview_permissions",
                    apply=True,
                    reviewed_revocations=review_path,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

            dataview.project = self.destination_project
            dataview.save(update_fields=["project", "date_modified"])
            self._write_review(review_path, fieldnames, approved)
            assign_perm("move_xform", self.alice, self.foreign_xform)
            with self.assertRaisesMessage(CommandError, "target-XForm permissions"):
                call_command(
                    "audit_cross_project_dataview_permissions",
                    apply=True,
                    reviewed_revocations=review_path,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        dataview.refresh_from_db()
        self.assertIsNone(dataview.deleted_at)
        self.assertTrue(
            XFormUserObjectPermission.objects.filter(
                content_object=self.foreign_xform, user=self.alice
            ).exists()
        )
        self.assertTrue(
            XFormGroupObjectPermission.objects.filter(
                content_object=self.foreign_xform, group=self.team
            ).exists()
        )
