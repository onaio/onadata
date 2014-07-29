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
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()

    def test_add_media_metadata(self):
        count = MetaData.objects.count()
        media_path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "screenshot.png")
        with open(media_path) as media_file:
            data = {
                'data_type': 'media',
                'data_file': media_file,
                'xform': self.xform.pk
            }
            request = self.factory.post('/', data)
            response = self.view(request)
            self.assertEqual(response.status_code, 201)
            another_count = MetaData.objects.count()
            self.assertEqual(another_count, count + 1)
