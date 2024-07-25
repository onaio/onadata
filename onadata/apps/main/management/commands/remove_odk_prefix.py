# -*- coding: utf-8 -*-
"""
remove_odk_prefix - removes the odk prefix from logger and viewer apps.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils.translation import gettext_lazy


class Command(BaseCommand):
    """
    remove_odk_prefix - removes the odk prefix from logger and viewer apps.
    """

    help = gettext_lazy("Remove from logger and viewer apps")

    def handle(self, *args, **kwargs):
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE south_migrationhistory SET app_name=%s WHERE app_name=%s",
            ["logger", "odk_logger"],
        )
        cursor.execute(
            "UPDATE south_migrationhistory SET app_name=%s WHERE app_name=%s",
            ["viewer", "odk_viewer"],
        )
