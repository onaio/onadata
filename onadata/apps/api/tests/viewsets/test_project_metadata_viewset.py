import os

from django.conf import settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.project_metadata_viewset import (
    ProjectMetaDataViewSet)
from onadata.apps.main.models.meta_data import (
    MetaData, XFormMetaData, ProjectMetaData)


class TestProjectMetaDataViewSet(TestAbstractViewSet):
    def setUp(self):
        super(TestProjectMetaDataViewSet, self).setUp()
        self.view = ProjectMetaDataViewSet.as_view({
            'delete': 'destroy',
            'get': 'retrieve',
            'post': 'create'
        })
        self._publish_xls_form_to_project()
        self.data_value = "screenshot.png"
        self.fixture_dir = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation"
        )
        self.path = os.path.join(self.fixture_dir, self.data_value)

    def _add_project_metadata(self, project, data_type, data_value, path=None):
        data = {
            'data_type': data_type,
            'data_value': data_value,
            'project': project.id
        }

        if path and data_value:
            with open(path) as media_file:
                data.update({
                    'data_file': media_file,
                })
                self._post_to_viewset(data)
        else:
            self._post_to_viewset(data)

    def _post_to_viewset(self, data, test=True):
        count = ProjectMetaData.objects.count()
        view = ProjectMetaDataViewSet.as_view({"post": "create"})
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        if test:
            self.assertEqual(response.status_code, 201)
            another_count = ProjectMetaData.objects.count()
            self.assertEqual(another_count, count + 1)
            self.project_metadata = ProjectMetaData.objects.get(
                pk=response.data['id'])

        return response

    def test_add_metadata_with_file_attachment(self):
        for data_type in ['supporting_doc', 'media']:
            self._add_project_metadata(
                self.project, data_type, self.data_value, self.path)
