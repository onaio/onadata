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
        metadata = [
            a
            for a in MetaData.objects.filter(
                data_type='published_by_formbuilder'
            )
            if isinstance(a.content_object, XForm)
        ]

        for obj in metadata:
            if obj.data_value == '' and obj.content_object.id_string in uids:
                MetaData.published_by_formbuilder(obj.content_object, 'True')

        self.stdout.write(
            "Done creating published_by_formbuilder metadata!!!"
        )
