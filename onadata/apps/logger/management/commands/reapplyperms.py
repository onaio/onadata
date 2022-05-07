#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4
"""
reapplyperms - reapplies XForm permissions for the given user.
"""
import gc
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from multidb.pinning import use_master

from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.project_utils import set_project_perms_to_xform

DEFAULT_SECONDS = 30 * 60


class Command(BaseCommand):
    """Reapply permissions to XForms."""

    help = _("Reapply permissions to XForms.")

    def _reapply_perms(self, username=None, days=None, seconds=None):
        xforms = XForm.objects.none()
        the_past = None

        if username:
            xforms = XForm.objects.filter(user__username=username)
        else:
            if days:
                the_past = timezone.now() - timedelta(days=days)

            if seconds:
                the_past = timezone.now() - timedelta(seconds=seconds)

            if the_past:
                xforms = XForm.objects.filter(
                    Q(date_created__gte=the_past) | Q(date_modified__gte=the_past)
                )

        self.stdout.write(_(f"{xforms.count()} to be updated"))

        with use_master:
            for xform in queryset_iterator(xforms):
                set_project_perms_to_xform(xform, xform.project)
                self.stdout.write(_(f"Updated permissions for XForm ID: {xform.id}"))
                gc.collect()

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", dest="days", type=int, default=0, help=_("No of days")
        )
        parser.add_argument(
            "--seconds",
            dest="seconds",
            type=int,
            default=DEFAULT_SECONDS,
            help=_("No of seconds"),
        )
        parser.add_argument(
            "--username", dest="username", default=None, help=_("Username")
        )

    # pylint: disable=unused-argument
    def handle(self, *args, **options):
        days = int(options["days"]) if "days" in options else 0
        seconds = int(options["seconds"]) if "seconds" in options else DEFAULT_SECONDS
        username = options["username"] if "username" in options else None

        if username:
            self._reapply_perms(username=str(username))
        else:
            if days > 0:
                self._reapply_perms(days=days)
            else:
                self._reapply_perms(seconds=seconds)
