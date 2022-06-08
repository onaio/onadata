from rest_framework.test import APIRequestFactory
from django.contrib.gis.geos import GeometryCollection, Point

from onadata.libs.serializers.geojson_serializer import\
    GeoJsonSerializer
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet


class TestGeoJsonSerializer(TestAbstractViewSet):

    def setUp(self):
        self._login_user_and_profile()
        self.factory = APIRequestFactory()

    def test_geojson_serializer(self):
        self._publish_xls_form_to_project()
        data = {
            'xform': self.xform.id,
            'geom': GeometryCollection(Point([6.707548, 6.423264]))
        }
        request = self.factory.get('/', **self.extra)
        serializer = GeoJsonSerializer(
            data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())
        geometry = serializer.validated_data['geom']
        self.assertEqual(geometry.geojson, data.get('geom').geojson)
