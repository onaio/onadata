# -*- coding: utf-8 -*-
"""
Export all gps points with their timestamps
"""
import csv

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models import Instance
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """Export all gps points with their timestamps"""

    help = gettext_lazy("Export all gps points with their timestamps")

    def handle(self, *args, **kwargs):
        with open("gps_points_export.csv", "w", encoding="utf-8") as csvfile:
            fieldnames = ["longitude", "latitude", "date_created"]
            writer = csv.writer(csvfile)
            writer.writerow(fieldnames)

            for instance in queryset_iterator(
                Instance.objects.exclude(geom__isnull=True)
            ):
                if hasattr(instance, "point") and instance.point is not None:
                    longitude = instance.point.coords[0]
                    latitude = instance.point.coords[1]
                    writer.writerow([longitude, latitude, instance.date_created])
        self.stdout.write("Export of gps files has completed!!!!")
