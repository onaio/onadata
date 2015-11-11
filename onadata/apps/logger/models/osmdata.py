from jsonfield import JSONField

from django.contrib.gis.db import models

from onadata.apps.logger.models.instance import Instance


class OsmData(models.Model):
    """
    OSM Data information from a submission instance
    """
    instance = models.ForeignKey(Instance, related_name='osm_data')
    xml = models.TextField()
    osm_id = models.CharField(max_length=10)
    osm_type = models.CharField(max_length=10, default='way')
    tags = JSONField(default={}, null=False)
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
            '''SELECT DISTINCT JSON_OBJECT_KEYS(tags) as id FROM "logger_osmdata" INNER JOIN "logger_instance" ON ( "logger_osmdata"."instance_id" = "logger_instance"."id" ) WHERE "logger_instance"."xform_id" = %s AND field_name = %s''',  # noqa
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
