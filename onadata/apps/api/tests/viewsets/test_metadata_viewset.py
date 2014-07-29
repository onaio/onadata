import os

from django.conf import settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.main.models.meta_data import MetaData


class TestMetaDataViewSet(TestAbstractViewSet):
    def setUp(self):
        super(TestMetaDataViewSet, self).setUp()
        self.view = MetaDataViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()
        self.data_value = "screenshot.png"
        self.path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", self.data_value)

    def test_add_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)

    def test_add_mapbox_layer(self):
        data_type = 'mapbox_layer'
        data_value = 'test_mapbox_layer||http://0.0.0.0:8080||attribution'
        self._add_form_metadata(self.xform, data_type, data_value)

    def test_delete_metadata(self):
        for data_type in ['supporting_doc', 'media', 'source']:
            count = MetaData.objects.count()
            self._add_form_metadata(self.xform, data_type,
                                    self.data_value, self.path)
            request = self.factory.delete('/')
            response = self.view(request, pk=self.metadata.pk)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(count, MetaData.objects.count())
