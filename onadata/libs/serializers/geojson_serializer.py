from rest_framework_gis.serializers import GeoFeatureModelSerializer

from onadata.apps.logger.models.instance import Instance


class GeoJsonSerializer(GeoFeatureModelSerializer):


    class Meta:
        model = Instance
        geo_field = "geom"

        fields = ('id', 'xform')