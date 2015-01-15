import geojson

from rest_framework_gis import serializers

from onadata.apps.logger.models.instance import Instance


class GeoJsonSerializer(serializers.GeoFeatureModelSerializer):

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super(GeoJsonSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    def to_native(self, obj):

        if obj is None:
            return super(GeoJsonSerializer, self).to_native(obj)

        if 'fields' in obj:
            fields = obj.get('fields').split(',')

        if 'instance' in obj:
            instance = obj.get('instance')

        if 'geo_field' in obj:
            geo_field = obj.get('geo_field')

        if not geo_field:
            return super(GeoJsonSerializer, self).to_native(
                obj.get('instance'))

        if instance:
            data = instance.get_dict()

        points = data.get(geo_field).split(';')

        if len(points) == 1:
            # point
            point = points[0].split()
            geometry = geojson.Point((float(point[1]), float(point[0])))
        elif len(points) > 1:
            pnt_list = []
            for pnt in points:
                point = pnt.split()
                pnt_list.append((float(point[1]), float(point[0])))

            if pnt_list[0] == pnt_list[len(pnt_list)-1]:
                geometry = geojson.Polygon([pnt_list])
            else:
                geometry = geojson.LineString(pnt_list)

        properties = {
            "_record_id": obj.get('instance').pk,
            "_field": geo_field
        }

        for field in fields:
            properties.update(field, data.get('field'))

        feature = geojson.Feature(geometry=geometry,
                                  id=obj.get('instance').pk,
                                  properties=properties)
        return feature

    class Meta:
        model = Instance
        geo_field = "geom"
        lookup_field = 'pk'
        id_field = False

        fields = ('id', 'xform')


class GeoJsonListSerializer(GeoJsonSerializer):

    def to_native(self, obj):
        instances = [inst for inst in obj[0].instances.all()]

        return [super(GeoJsonListSerializer, self).to_native(ret)
                for ret in instances]
