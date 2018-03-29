# -*- coding: utf-8 -*-
"""
OSM Data model class
"""
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField


class OsmData(models.Model):
    """
    OSM Data information from a submission instance
    """
    instance = models.ForeignKey('logger.Instance', related_name='osm_data')
    xml = models.TextField()
    osm_id = models.CharField(max_length=20)
    osm_type = models.CharField(max_length=10, default='way')
    tags = JSONField(default=dict, null=False)
    geom = models.GeometryCollectionField()
    filename = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255, blank=True, default='')

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, default=None)

    class Meta:
        app_label = 'logger'
        unique_together = ('instance', 'field_name')

    @classmethod
    def get_tag_keys(cls, xform, field_path, include_prefix=False):
        query = OsmData.objects.raw(
            '''SELECT DISTINCT JSONB_OBJECT_KEYS(tags) as id FROM "logger_osmdata" INNER JOIN "logger_instance" ON ( "logger_osmdata"."instance_id" = "logger_instance"."id" ) WHERE "logger_instance"."xform_id" = %s AND field_name = %s''',  # noqa
            [xform.pk, field_path]
        )
        prefix = field_path + u':' if include_prefix else u''

        return sorted([prefix + key.id for key in query])

    def get_tags_with_prefix(self):
        doc = {
            self.field_name + ':' + self.osm_type + ':id': self.osm_id
        }
        for k, v in self.tags.items():
            doc[self.field_name + ':' + k] = v

        return doc

    def _set_centroid_in_tags(self):
        self.tags = self.tags if isinstance(self.tags, dict) else {}
        if self.geom is not None:
            # pylint: disable=E1101
            self.tags.update({
                "ctr:lon": self.geom.centroid.x,
                "ctr:lat": self.geom.centroid.y,
            })

    def save(self, *args, **kwargs):
        self._set_centroid_in_tags()
        super(OsmData, self).save(*args, **kwargs)
