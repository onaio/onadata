from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.main.models import MetaData
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Set media file_hash for all existing media files")

    option_list = BaseCommand.option_list

    def handle(self, *args, **kwargs):
        for media in queryset_iterator(MetaData.objects.exclude(data_file='')):
            if media.data_file:
                media.file_hash = media._set_hash()
                media.save()
