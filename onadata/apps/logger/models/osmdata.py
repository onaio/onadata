from jsonfield import JSONField

from django.contrib.gis.db import models

from onadata.apps.logger.models.instance import Instance


class OSMData(models.Model):
    """
    OSM Data information from a submission instance
    """
    instance = models.ForeignKey(Instance, related_name='osm_data')
    xml = models.TextField()
    osm_id = models.CharField(max_length=10)
    tags = JSONField(default={}, null=False)
    geom = models.GeometryCollectionField()
    filename = models.CharField(max_length=255)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)
