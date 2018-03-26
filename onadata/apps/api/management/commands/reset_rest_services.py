from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.apps.restservice.models import RestService
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Removes old bamboo rest services and ensures date modified is "
             u"not null")

    def handle(self, *args, **options):
        self.stdout.write("Task started ...")

        # Delete old bamboo rest service
        RestService.objects.filter(name='bamboo').delete()

        # Get all the rest services
        for rest in queryset_iterator(RestService.objects.all()):
            rest.save()

        self.stdout.write("Task ended ...")
