#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
import gc

from django.utils import timezone
from datetime import timedelta
from onadata.apps.logger.models import XForm
from django.db.models import Q
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy as _

from multidb.pinning import use_master

from onadata.libs.utils.project_utils import set_project_perms_to_xform
from onadata.libs.utils.model_tools import queryset_iterator

DEFAULT_SECONDS = 30 * 60


class Command(BaseCommand):
    help = _("Reapply permissions to XForms.")

    def _reapply_perms(self, days=None, seconds=None):
        the_past = None

        if days:
            the_past = timezone.now() - timedelta(days=days)

        if seconds:
            the_past = timezone.now() - timedelta(seconds=seconds)

        if the_past:
            xforms = XForm.objects.filter(
                Q(date_created__gte=the_past) | Q(date_modified__gte=the_past))

            self.stdout.write(_("{} to be updated").format(xforms.count()))

            with use_master:
                for xform in queryset_iterator(xforms):
                    set_project_perms_to_xform(xform, xform.project)
                    print(gc.collect())

    def add_arguments(self, parser):
        parser.add_argument('--days', dest='days', type=int, default=0,
                            help=_("No of days"))
        parser.add_argument('--seconds', dest='seconds', type=int,
                            default=DEFAULT_SECONDS, help=_("No of seconds"))

    def handle(self, *args, **options):
        days = int(options['days']) if 'days' in options else 0
        seconds = int(options['seconds']) if 'seconds' in options else \
            DEFAULT_SECONDS

        if days > 0:
            self._reapply_perms(days=days)
        else:
            self._reapply_perms(seconds=seconds)
