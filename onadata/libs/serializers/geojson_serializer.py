import geojson

from rest_framework_gis import serializers

from onadata.apps.logger.models.instance import Instance


def create_feature(instance, geo_field, fields):
    """
    Create a geojson feature from a single instance
    """
    data = instance.get_dict()

    if geo_field not in data:
        # Return an empty feature
        return geojson.Feature()

    points = data.get(geo_field).split(';')

    if len(points) == 1:
            # only one set of coordinates -> Point
            point = points[0].split()
            geometry = geojson.Point((float(point[1]), float(point[0])))
    elif len(points) > 1:
        # More than one set of coordinates -> Either LineString or Polyon
        pnt_list = []
        for pnt in points:
            point = pnt.split()
            pnt_list.append((float(point[1]), float(point[0])))

        if pnt_list[0] == pnt_list[len(pnt_list)-1]:
            # First and last point are same -> Polygon
            geometry = geojson.Polygon([pnt_list])
        else:
            # First and last point not same -> LineString
            geometry = geojson.LineString(pnt_list)

    # set the default properties
    properties = {
        "_record_id": instance.pk,
        "_field": geo_field
    }

    # Add additional parameters added by the user
    if fields:
        for field in fields:
            properties.update(field, data.get('field'))

    return geojson.Feature(geometry=geometry,
                           id=instance.pk,
                           properties=properties)


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
        geo_field = None
        fields = None

        if 'fields' in obj and obj.get('fields'):
            fields = obj.get('fields').split(',')

        if 'instance' in obj and obj.get('instance'):
            instance = obj.get('instance')

        if 'geo_field' in obj and obj.get('geo_field'):
            geo_field = obj.get('geo_field')

        if geo_field:
            return create_feature(instance, geo_field, fields)

        # Use the default serializer
        return super(GeoJsonSerializer, self).to_native(instance)

    class Meta:
        model = Instance
        geo_field = "geom"
        lookup_field = 'pk'
        id_field = False

        fields = ('id', 'xform')


class GeoJsonListSerializer(GeoJsonSerializer):
    """
    Creates a FeatureCollections
    """

    def to_native(self, obj):

        if obj is None:
            return super(GeoJsonSerializer, self).to_native(obj)

        geo_field = None
        fields = None

        if 'fields' in obj and obj.get('fields'):
            fields = obj.get('fields').split(',')

        if 'instances' in obj and obj.get('instances'):
            insts = obj.get('instances')

        if 'geo_field' in obj and obj.get('geo_field'):
            geo_field = obj.get('geo_field')

        # Get the instances from the form
        instances = [inst for inst in insts[0].instances.all()]

        if not geo_field:
            return geojson.FeatureCollection(
                [super(GeoJsonListSerializer, self).to_native(
                    {'instance': ret})for ret in instances])

        # Use the default serializer
        return geojson.FeatureCollection(
            [create_feature(ret, geo_field, fields)for ret in instances])
