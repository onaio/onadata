import geojson
import json

from rest_framework_gis import serializers

from onadata.apps.logger.models.instance import Instance


def create_feature(instance, geo_field, fields):
    """
    Create a geojson feature from a single instance
    """
    data = instance.json

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
    properties = {}

    # Add additional parameters added by the user
    if fields:
        for field in fields:
            properties.update({field: data.get(field)})
    else:
        properties.update(data)

    return geojson.Feature(geometry=geometry,
                           id=instance.pk,
                           properties=properties)


def is_polygon(point_list):
    """Takes a list of tuples and determines if it is a polygon"""
    return (len(point_list) > 1 and
            point_list[0] == point_list[len(point_list)-1])


def geometry_from_string(points):
    """Takes a string, returns a geometry object"""

    points = points.split(';')
    pnt_list = [tuple(map(float, reversed(point.split()[:2])))
                for point in points]

    if len(pnt_list) == 1:
        geometry = geojson.GeometryCollection(
            [geojson.Point(pnt_list[0])])
    elif is_polygon(pnt_list):
        # First and last point are same -> Polygon
        geometry = geojson.Polygon([pnt_list])
    else:
        # First and last point not same -> LineString
        geometry = geojson.LineString(pnt_list)

    return geometry


class GeometryField(serializers.GeometryField):
    def to_representation(self, value):
        if isinstance(value, dict) or value is None:
            return None

        return json.loads(value.geojson)


class GeoJsonSerializer(serializers.GeoFeatureModelSerializer):

    geom = GeometryField()

    class Meta:
        model = Instance
        geo_field = "geom"
        lookup_field = 'pk'
        id_field = False
        fields = ('id', 'xform')

    def to_representation(self, obj):
        ret = super(GeoJsonSerializer, self).to_representation(obj)
        request = self.context.get('request')

        if obj and ret and 'properties' in ret and request is not None:
            fields = request.query_params.get('fields')
            if fields:
                for field in fields.split(','):
                    ret['properties'][field] = obj.json.get(field)

        if obj and ret and request:
            geo_field = request.query_params.get('geo_field')
            if geo_field:
                points = obj.json.get(geo_field)
                geometry = geometry_from_string(points) \
                    if points else geojson.Feature()

                ret['geometry'] = geometry

        return ret


class GeoJsonListSerializer(GeoJsonSerializer):
    """
    Creates a FeatureCollections
    """

    def to_representation(self, obj):

        if obj is None:
            return super(GeoJsonSerializer, self).to_representation(obj)

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
                [super(GeoJsonListSerializer, self).to_representation(
                    {'instance': ret, 'fields': obj.get('fields')})
                 for ret in instances])

        # Use the default serializer
        return geojson.FeatureCollection(
            [create_feature(ret, geo_field, fields)for ret in instances])
