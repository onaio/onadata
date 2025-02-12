# -*- coding: utf-8 -*-
"""
The GeoJsonSerializer class - uses the GeoJSON structure for submission data.
"""
import json

import geojson
from rest_framework_gis import serializers

from onadata.apps.logger.models.instance import Instance
from onadata.libs.utils.common_tools import str_to_bool
from onadata.libs.utils.dict_tools import get_values_matching_key


def create_feature(instance, geo_field, fields):
    """
    Create a geojson feature from a single instance
    """
    data = instance.json
    geometry = None

    if geo_field not in data:
        # Return an empty feature
        return geojson.Feature()

    points = data.get(geo_field).split(";")

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

        if pnt_list[0] == pnt_list[len(pnt_list) - 1]:
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

    return geojson.Feature(geometry=geometry, id=instance.pk, properties=properties)


def is_polygon(point_list):
    """Takes a list of tuples and determines if it is a polygon"""
    return len(point_list) > 1 and point_list[0] == point_list[len(point_list) - 1]


def geometry_from_string(points, simple_style):
    """
    Takes a string, returns a geometry object.
    `simple_style` param allows building geojson
    that adheres to the simplestyle-spec
    """
    points = points.split(";")
    pnt_list = [tuple(map(float, reversed(point.split()[:2]))) for point in points]

    if len(pnt_list) == 1:
        geometry = (
            geojson.Point(pnt_list[0])
            if str_to_bool(simple_style)
            else geojson.GeometryCollection([geojson.Point(pnt_list[0])])
        )
    elif is_polygon(pnt_list):
        # First and last point are same -> Polygon
        geometry = geojson.Polygon([pnt_list])
    else:
        # First and last point not same -> LineString
        geometry = geojson.LineString(pnt_list)

    return geometry


class GeometryField(serializers.GeometryField):
    """
    The GeometryField class - representation for single GeometryField.
    """

    def to_representation(self, value):
        if isinstance(value, dict) or value is None:
            return None

        return json.loads(value.geojson)


class GeoJsonSerializer(serializers.GeoFeatureModelSerializer):
    """
    The GeoJsonSerializer class - uses the GeoJSON structure for submission data.
    """

    geom = GeometryField()

    class Meta:
        model = Instance
        geo_field = "geom"
        lookup_field = "pk"
        id_field = False
        fields = ("id", "xform")

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")

        if instance and ret and "properties" in ret and request is not None:
            fields = request.query_params.get("fields")
            if fields:
                for field in fields.split(","):
                    ret["properties"][field] = instance.json.get(field)

        if instance and ret and request:
            fields = request.query_params.get("fields")
            geo_field = request.query_params.get("geo_field")
            simple_style = request.query_params.get("simple_style")
            title = request.query_params.get("title")

            if fields:
                for field in fields.split(","):
                    ret["properties"][field] = instance.json.get(field)

            if geo_field:
                xform = instance.xform
                geotrace_xpaths = xform.geotrace_xpaths()
                polygon_xpaths = xform.polygon_xpaths()
                if "properties" in ret:
                    if title:
                        ret["properties"]["title"] = instance.json.get(title)
                points = instance.json.get(geo_field)
                if geo_field in geotrace_xpaths or geo_field in polygon_xpaths:
                    value = get_values_matching_key(instance.json, geo_field)
                    # handle empty geoms
                    try:
                        points = next(value)
                    except StopIteration:
                        points = None
                geometry = (
                    geometry_from_string(points, simple_style)
                    if points and isinstance(points, str)
                    else None
                )

                ret["geometry"] = geometry

        return ret


class GeoJsonListSerializer(GeoJsonSerializer):
    """
    Creates a FeatureCollections
    """

    def to_representation(self, instance):

        if instance is None:
            return super().to_representation(instance)
        geo_field = None
        fields = None
        insts = None

        if "fields" in instance and instance.get("fields"):
            fields = instance.get("fields").split(",")

        if "instances" in instance and instance.get("instances"):
            insts = instance.get("instances")

        if "geo_field" in instance and instance.get("geo_field"):
            geo_field = instance.get("geo_field")

        # Get the instances from the form
        instances = insts[0].instances.all()

        if not geo_field:
            return geojson.FeatureCollection(
                [
                    super().to_representation(
                        {"instance": ret, "fields": instance.get("fields")}
                    )
                    for ret in instances
                ]
            )

        # Use the default serializer
        return geojson.FeatureCollection(
            [create_feature(ret, geo_field, fields) for ret in instances]
        )
