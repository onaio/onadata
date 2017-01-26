#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from django.db import connection
from onadata.apps.main.models import MetaData
from onadata.apps.logger.models import XForm


class Command(BaseCommand):
    help = ugettext_lazy("Create metadata for kpi forms that are not editable")

    def handle(self, *args, **kwargs):
        cursor = connection.cursor()
        cursor.execute(
            'SELECT uid FROM kpi_asset WHERE asset_type=%s', ['survey'])
        rs = cursor.cursor.fetchall()
        uids = [a[0] for a in rs]
        xforms = XForm.objects.filter(id_string__in=uids)
        for x in xforms:
            MetaData.published_by_formbuilder(x, 'True')

        self.stdout.write(
            "Done creating published_by_formbuilder metadata!!!"
        )
