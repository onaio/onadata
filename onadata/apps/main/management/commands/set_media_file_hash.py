# -*- coding: utf-8 -*-
"""set_media_file_hash command - (re)apply the hash of all media files."""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.main.models import MetaData
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """Set media file_hash for all existing media files"""

    help = gettext_lazy("Set media file_hash for all existing media files")

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        """Set media file_hash for all existing media files"""
        for media in queryset_iterator(MetaData.objects.exclude(data_file="")):
            if media.data_file:
                media.file_hash = media.set_hash()
                media.save()
