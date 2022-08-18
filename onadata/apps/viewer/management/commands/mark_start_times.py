# -*- coding: utf-8 -*-
"""
mark_start_times command - This is a one-time command to mark start times of old surveys
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.viewer.models.data_dictionary import DataDictionary


class Command(BaseCommand):
    """
    This is a one-time command to mark start times of old surveys.
    """

    help = gettext_lazy(
        "This is a one-time command to mark start times of old surveys."
    )

    def handle(self, *args, **kwargs):
        for xform in DataDictionary.objects.all():
            xform.mark_start_time_boolean()
            xform.save()
