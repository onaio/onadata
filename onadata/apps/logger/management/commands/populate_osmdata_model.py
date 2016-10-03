from django.utils.translation import ugettext_lazy
from django.core.management.base import BaseCommand

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.osm import save_osm_data


class Command(BaseCommand):
    args = '<username>'
    help = ugettext_lazy("Populate OsmData model with osm info.")

    def handle(self, *args, **kwargs):
        xforms = XForm.objects.filter(instances_with_osm=True)

        # username
        if args:
            xforms = xforms.filter(user__username=args[0])

        for xform in queryset_iterator(xforms):
            attachments = Attachment.objects.filter(
                extension=Attachment.OSM,
                instance__xform=xform
            ).distinct('instance')

            count = attachments.count()
            c = 0
            for a in queryset_iterator(attachments):
                pk = a.instance.parsed_instance.pk
                save_osm_data(pk)
                c += 1
                if c % 1000 == 0:
                    self.stdout.write("%s:%s: Processed %s of %s." %
                                      (xform.user.username,
                                       xform.id_string, c, count))

            self.stdout.write("%s:%s: processed %s of %s submissions." %
                              (xform.user.username, xform.id_string, c, count))
