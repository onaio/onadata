#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
Fix num of submissions
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.models.xform import clear_project_cache
from onadata.apps.main.models import UserProfile
from onadata.libs.utils.cache_tools import XFORM_COUNT, safe_cache_delete


class Command(BaseCommand):
    """Fix num of submissions"""

    help = gettext("Fix num of submissions")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report incorrect submission counts without updating them.",
        )

    def _repair_xform(self, xform, expected_count, dry_run):
        if xform.num_of_submissions == expected_count:
            return False

        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            f"{action} form {xform.pk} ({xform.id_string}): "
            f"{xform.num_of_submissions} -> {expected_count}"
        )

        if not dry_run:
            with transaction.atomic():
                xform.num_of_submissions = expected_count
                xform.save(update_fields=["num_of_submissions"])

        return True

    def _repair_profile(self, profile, expected_count, dry_run):
        if profile.num_of_submissions == expected_count:
            return False

        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            f"{action} profile {profile.pk} ({profile.user.username}): "
            f"{profile.num_of_submissions} -> {expected_count}"
        )

        if not dry_run:
            with transaction.atomic():
                profile.num_of_submissions = expected_count
                profile.save(update_fields=["num_of_submissions"])

        return True

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        form_mismatches = 0
        profile_mismatches = 0
        project_ids = set()

        for xform in XForm.objects.filter(
            downloadable=True, is_merged_dataset=False
        ).iterator():
            expected_count = xform.instances.filter(deleted_at__isnull=True).count()
            form_mismatches += self._repair_xform(xform, expected_count, dry_run)

            if not dry_run:
                safe_cache_delete(f"{XFORM_COUNT}{xform.pk}")
                project_ids.add(xform.project_id)

        # Merged dataset counts depend on their constituent forms, so repair
        # them only after all regular forms have been processed.
        for xform in XForm.objects.filter(
            downloadable=True, is_merged_dataset=True
        ).iterator():
            child_ids = xform.mergedxform.xforms.values_list("pk", flat=True)
            expected_count = Instance.objects.filter(
                xform_id__in=child_ids, deleted_at__isnull=True
            ).count()
            form_mismatches += self._repair_xform(xform, expected_count, dry_run)

            if not dry_run:
                safe_cache_delete(f"{XFORM_COUNT}{xform.pk}")
                project_ids.add(xform.project_id)

        for profile in UserProfile.objects.select_related("user").iterator():
            expected_count = Instance.objects.filter(
                deleted_at__isnull=True, xform__user_id=profile.user_id
            ).count()
            profile_mismatches += self._repair_profile(profile, expected_count, dry_run)

        if not dry_run:
            for project_id in project_ids:
                clear_project_cache(project_id)

        verb = "Found" if dry_run else "Repaired"
        self.stdout.write(
            f"{verb} {form_mismatches} form count mismatch(es) and "
            f"{profile_mismatches} profile count mismatch(es)."
        )
