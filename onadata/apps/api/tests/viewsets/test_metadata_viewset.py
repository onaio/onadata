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

    def test_add_media_metadata(self):
        data_value = "screenshot.png"
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", data_value)
        self._add_form_metadata(self.xform, 'media', data_value, path)

    def test_add_supporting_document(self):
        data_value = "transportation.xls"
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", data_value)
        self._add_form_metadata(self.xform, 'supporting_doc', data_value, path)
