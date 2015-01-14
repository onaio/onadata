from rest_framework_gis.serializers import GeoFeatureModelSerializer

from onadata.apps.logger.models.instance import Instance


class GeoJsonSerializer(GeoFeatureModelSerializer):

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
