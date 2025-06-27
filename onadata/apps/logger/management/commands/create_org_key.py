#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4
"""
create_org_key - creates KMS keys for organizations.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.libs.kms.tools import create_key
from onadata.libs.utils.model_tools import queryset_iterator

User = get_user_model()


class Command(BaseCommand):
    """Create KMS keys for organizations.

    Usage:
        python manage.py create_org_key --usernames <username1> <username2> ...
        python manage.py create_org_key --all
        python manage.py create_org_key --dry-run
    """

    help = _("Create KMS keys for organizations.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--usernames",
            dest="usernames",
            nargs="+",
            help=_("List of organization usernames to create keys for"),
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_orgs",
            help=_("Create keys for all organizations"),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help=_("Show what would be done without actually creating keys"),
        )

    def handle(self, *args, **options):
        usernames = options.get("usernames")
        all_orgs = options.get("all_orgs")
        dry_run = options.get("dry_run")

        if not usernames and not all_orgs:
            self.stdout.write(
                self.style.ERROR(_("Please specify either --usernames or --all"))
            )
            return

        if usernames and all_orgs:
            self.stdout.write(
                self.style.ERROR(
                    _("Please specify either --usernames or --all, not both")
                )
            )
            return

        # Get organizations to process
        if usernames:
            organizations = OrganizationProfile.objects.filter(
                user__username__in=usernames,
                user__is_active=True,
            )
            self.stdout.write(
                _(
                    f"Processing {organizations.count()} organizations: {', '.join(usernames)}"
                )
            )
        else:
            organizations = OrganizationProfile.objects.filter(user__is_active=True)
            self.stdout.write(
                _(f"Processing all {organizations.count()} organizations")
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(_("DRY RUN MODE - No keys will be created"))
            )

        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        created_count = 0
        skipped_count = 0
        error_count = 0

        for org in queryset_iterator(organizations):
            try:
                # Check if organization already has an active key
                active_key_exists = KMSKey.objects.filter(
                    content_type=content_type,
                    object_id=org.pk,
                    is_active=True,
                ).exists()

                if active_key_exists:
                    self.stdout.write(
                        _(f"Skipping {org.user.username} - already has active key")
                    )
                    skipped_count += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        _(f"Would create key for organization: {org.user.username}")
                    )
                    created_count += 1
                else:
                    # Create the key
                    key = create_key(org, created_by=None)
                    self.stdout.write(
                        _(
                            f"Created key {key.key_id} for organization: {org.user.username}"
                        )
                    )
                    created_count += 1

            except Exception as exc:  # pylint: disable=broad-exception-caught
                self.stdout.write(
                    self.style.ERROR(
                        _(f"Error creating key for {org.user.username}: {str(exc)}")
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write("")
        self.stdout.write(_("Summary:"))
        self.stdout.write(_(f"  Created: {created_count}"))
        self.stdout.write(_(f"  Skipped: {skipped_count}"))
        self.stdout.write(_(f"  Errors: {error_count}"))
        self.stdout.write(
            _(f"  Total processed: {created_count + skipped_count + error_count}")
        )
