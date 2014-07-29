import os

from django.conf import settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet


class TestMetaDataViewSet(TestAbstractViewSet):
    def setUp(self):
        super(TestMetaDataViewSet, self).setUp()
        self.view = MetaDataViewSet.as_view({
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()

    def test_add_metadat_with_file_attachment(self):
        data_value = "screenshot.png"
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", data_value)
        for data_type in ['supporting_doc', 'media', 'source']:
            self._add_form_metadata(self.xform, data_type, data_value, path)

    def test_add_mapbox_layer(self):
        data_type = 'mapbox_layer'
        data_value = 'test_mapbox_layer||http://0.0.0.0:8080||attribution'
        self._add_form_metadata(self.xform, data_type, data_value)
