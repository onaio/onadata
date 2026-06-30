# -*- coding: utf-8 -*-
"""
Reactivate users disabled by the inactive-account lifecycle.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.translation import gettext_lazy

from onadata.apps.main.models.user_deactivation import (
    UserDeactivationState,
    has_current_deactivation,
    reactivate_user,
)

User = get_user_model()
AMBIGUOUS_USER = object()


class Command(BaseCommand):
    """Reactivate inactive-account lifecycle users."""

    help = gettext_lazy("Reactivate users disabled by inactive-account lifecycle.")

    def add_arguments(self, parser):
        parser.add_argument(
            "users",
            nargs="+",
            help=gettext_lazy("One or more usernames or numeric user IDs."),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=gettext_lazy("Report users that would be reactivated."),
        )

    def handle(self, *args, **options):
        when = timezone.now()
        states_by_identifier = self._resolve_states(options["users"])
        reactivated_count = 0
        skipped_count = 0

        for identifier, state in states_by_identifier:
            if state is None:
                skipped_count += 1
                if options["verbosity"] > 0:
                    self.stdout.write(f"Skipped {identifier}: no lifecycle state.")
                continue

            if options["dry_run"]:
                if has_current_deactivation(state):
                    reactivated_count += 1
                    if options["verbosity"] > 0:
                        self.stdout.write(f"Would reactivate {state.user.username}.")
                else:
                    skipped_count += 1
                    if options["verbosity"] > 0:
                        self.stdout.write(
                            f"Skipped {state.user.username}: not currently deactivated."
                        )
                continue

            result = reactivate_user(state, when=when)
            if result.reactivated:
                reactivated_count += 1
                if options["verbosity"] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f"Reactivated {result.user.username}.")
                    )
            else:
                skipped_count += 1
                if options["verbosity"] > 0:
                    self.stdout.write(
                        f"Skipped {result.user.username}: not currently deactivated."
                    )

        if options["verbosity"] > 0:
            action = "Would reactivate" if options["dry_run"] else "Reactivated"
            self.stdout.write(
                f"{action} {reactivated_count} inactive users; "
                f"skipped {skipped_count}."
            )

    def _resolve_states(self, identifiers):
        resolved = []
        errors = []
        for identifier in identifiers:
            identifier = str(identifier)
            user = self._resolve_user(identifier)
            if user is AMBIGUOUS_USER:
                errors.append(
                    f"Ambiguous numeric user identifier: {identifier} matches "
                    "both a username and a user ID."
                )
                continue

            if user is None:
                errors.append(f"User not found: {identifier}")
                continue

            state = (
                UserDeactivationState.objects.select_related("user")
                .filter(user=user)
                .first()
            )
            resolved.append((identifier, state))

        if errors:
            raise CommandError("; ".join(errors))

        return resolved

    def _resolve_user(self, identifier):
        if not identifier.isdigit():
            return User.objects.filter(username=identifier).first()

        user_by_id = User.objects.filter(pk=int(identifier)).first()
        user_by_username = User.objects.filter(username=identifier).first()
        if (
            user_by_id is not None
            and user_by_username is not None
            and user_by_id.pk != user_by_username.pk
        ):
            return AMBIGUOUS_USER

        return user_by_id or user_by_username
