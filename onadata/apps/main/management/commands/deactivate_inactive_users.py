# -*- coding: utf-8 -*-
"""
Deactivate users due in the inactive-account lifecycle.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext_lazy

from onadata.apps.main.models.user_deactivation import (
    DEACTIVATION_ACTION_DEACTIVATE,
    get_pending_deactivation_actions,
    perform_deactivation_action,
)


class Command(BaseCommand):
    """Deactivate users due in the inactive-account lifecycle."""

    help = gettext_lazy("Deactivate users due in the inactive-account lifecycle.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=gettext_lazy("Report due deactivations without mutating users."),
        )

    def handle(self, *args, **options):
        when = timezone.now()
        deactivation_actions = [
            action
            for action in get_pending_deactivation_actions(when=when)
            if action.action == DEACTIVATION_ACTION_DEACTIVATE
        ]

        if options["dry_run"]:
            if options["verbosity"] > 0:
                self.stdout.write(
                    f"Would deactivate {len(deactivation_actions)} inactive users."
                )
            return

        deactivated_count = 0
        skipped_count = 0
        token_revocation_count = 0
        permission_snapshot_count = 0
        permission_revocation_count = 0

        for action in deactivation_actions:
            result = perform_deactivation_action(action, when=when)
            if result.deactivated:
                deactivated_count += 1
                token_revocation_count += result.token_revocation_count
                permission_snapshot_count += result.permission_snapshot_count
                permission_revocation_count += result.permission_revocation_count
            else:
                skipped_count += 1

        if options["verbosity"] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deactivated {deactivated_count} inactive users; "
                    f"skipped {skipped_count}; "
                    f"revoked {token_revocation_count} tokens; "
                    f"snapshotted {permission_snapshot_count} permissions; "
                    f"revoked {permission_revocation_count} permissions."
                )
            )
