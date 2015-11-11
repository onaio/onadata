from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy
from django.core.management.base import BaseCommand

from onadata.apps.logger.models import Attachment
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.osm import save_osm_data


class Command(BaseCommand):
    args = '<username>'
    help = ugettext_lazy("Populate OsmData model with osm info.")

    def handle(self, *args, **kwargs):

        attachments = Attachment.objects.filter(extension=Attachment.OSM)
        # username
        if args:
            users = User.objects.filter(username=args[0])
            attachments = attachments.filter(instance__xform__user__in=users)

        attachments = attachments.distinct('instance')

        count = attachments.count()
        c = 0
        for a in queryset_iterator(attachments):
            pk = a.instance.parsed_instance.pk
            save_osm_data(pk)
            c += 1
            if c % 1000 == 0:
                self.stdout.write("Processed %s of %s." % (c, count))

        self.stdout.write("Processed %s of %s submissions" % (c, count))
