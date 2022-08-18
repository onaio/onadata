#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""
Create metadata for kpi forms that are not editable
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from django.db import connection
from onadata.apps.main.models import MetaData
from onadata.apps.logger.models import XForm


class Command(BaseCommand):
    """Create metadata for kpi forms that are not editable"""

    help = gettext_lazy("Create metadata for kpi forms that are not editable")

    def handle(self, *args, **kwargs):
        cursor = connection.cursor()
        cursor.execute("SELECT uid FROM kpi_asset WHERE asset_type=%s", ["survey"])
        results = cursor.cursor.fetchall()
        uids = [a[0] for a in results]
        xforms = XForm.objects.filter(id_string__in=uids)
        for xform in xforms:
            MetaData.published_by_formbuilder(xform, "True")

        self.stdout.write("Done creating published_by_formbuilder metadata!!!")
