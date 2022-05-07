# -*- coding: utf-8 -*-
"""
populate_osmdata_model command - process OSM XML and save data in OsmData model/table.
"""
from django.utils.translation import gettext_lazy
from django.core.management.base import BaseCommand

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.osm import save_osm_data


class Command(BaseCommand):
    """Populate OsmData model with osm info."""

    args = "<username>"
    help = gettext_lazy("Populate OsmData model with osm info.")

    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        """Populate OsmData model with osm info."""
        xforms = XForm.objects.filter(instances_with_osm=True)

        # username
        if args:
            xforms = xforms.filter(user__username=args[0])

        for xform in queryset_iterator(xforms):
            attachments = Attachment.objects.filter(
                extension=Attachment.OSM, instance__xform=xform
            ).distinct("instance")

            count = attachments.count()
            counter = 0
            for attachment in queryset_iterator(attachments):
                instance_pk = attachment.instance.parsed_instance.pk
                save_osm_data(instance_pk)
                counter += 1
                if counter % 1000 == 0:
                    self.stdout.write(
                        f"{xform.user.username}:{xform.id_string}: "
                        f"Processed {counter} of {count}."
                    )

            self.stdout.write(
                f"{xform.user.username}:{xform.id_string}: "
                f"processed {counter} of {count} submissions."
            )
