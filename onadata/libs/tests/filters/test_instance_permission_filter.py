import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Project
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.main.models.meta_data import MetaData


class TestMetaDataFilter(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()
        self.extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        self.xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )

        self._publish_transportation_form_and_submit_instance()
        self.project = Project.objects.create(name="Test Project",
                                              organization=self.user,
                                              created_by=self.user)
        self.xform.project = self.project
        self.xform.save()

        self.instance = self.xform.instances.first()
        self._add_external_export_metadata(self.instance)

        self.view = MetaDataViewSet.as_view({'get': 'list'})

        ContentType.objects.get_or_create(app_label="logger", model="instance")

    def _add_external_export_metadata(self, content_object):
        MetaData.external_export(content_object,
                                 "https://test/external/export")

    def _create_dataview(self, xform, project, columns, query):
        self.data_view = DataView.objects.create(
            name="Test Dataview",
            xform=xform,
            project=project,
            columns=columns,
            query=query)

    def _add_multiple_submissions(self):
        for x in range(1, 9):
            path = os.path.join(
                settings.PROJECT_ROOT, 'libs', 'tests', "utils", 'fixtures',
                'tutorial', 'instances', 'uuid{}'.format(x), 'submission.xml')
            self._make_submission(path)
            x += 1

    def _setup_dataview_test_data(self, columns=None, query=None):
        columns = columns or ["name", "age", "gender"]
        query = query or [{"column": "age", "filter": ">", "value": "20"},
                          {"column": "age", "filter": "<", "value": "50"}]
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT, 'libs', 'tests', "utils", "fixtures",
            "tutorial.xls")

        self._publish_xls_file_and_set_xform(xlsform_path)

        self.xform.project = self.project
        self.xform.save()

        self._create_dataview(self.xform, self.project, columns, query)
        self._add_multiple_submissions()

    def test_metadata_filter_for_user_with_xform_perms(self):

        params = {"instance": self.instance.id,
                  "project": self.project.id,
                  "xform": self.xform.id}
        request = self.factory.get('/', data=params, **self.extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 1)

    def test_metadata_filter_for_user_without_xform_perms(self):
        self._create_user_and_login("alice", "password")
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        params = {"instance": self.instance.id,
                  "project": self.project.id,
                  "xform": self.xform.id}
        request = self.factory.get('/', data=params, **extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)

    def test_filter_for_foreign_instance_request(self):
        self._create_user_and_login("alice", "password")
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        project = Project.objects.create(name="Another Test Project",
                                         organization=self.user,
                                         created_by=self.user)
        self._publish_xls_file_and_set_xform(self.xls_file_path)
        self.xform.project = project
        self.xform.save()

        params = {"instance": self.instance.id,
                  "project": project.id,
                  "xform": self.xform.id}
        request = self.factory.get('/', data=params, **extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)

    def test_filter_for_dataview_metadata_instance_request(self):
        # """Dataview IDs should not yield any submission metadata"""
        self._setup_dataview_test_data()

        # retrieve the xform instance that is part of the dataview objects
        instance = self.xform.instances.last()
        # add metadata to instance
        self._add_external_export_metadata(instance)

        params = {"instance": instance.id,
                  "project": self.project.id,
                  "dataview": self.data_view.id}

        request = self.factory.get('/', data=params, **self.extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)

    def test_filter_given_user_without_permissions_to_xform(self):
        """Instance metadata isn't listed for users without form perms"""
        self._setup_dataview_test_data()

        # retrieve the xform instance that is part of the dataview objects
        instance = self.xform.instances.last()
        # add metadata to instance
        self._add_external_export_metadata(instance)

        self._create_user_and_login("alice", "password")

        project = Project.objects.create(name="Test Project",
                                         organization=self.user,
                                         created_by=self.user)

        params = {"instance": instance.id,
                  "project": project.id,
                  "dataview": self.data_view.id}

        request = self.factory.get('/', data=params, **self.extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)

    def test_filter_given_dataview_in_project_without_instance(self):
        """Meta data for submissions shouldn't be accessible from dataview"""

        data_view_query = [
            {"column": "gender", "filter": "=", "value": "female"}]
        self._setup_dataview_test_data(query=data_view_query)

        # retrieve the xform instance that is part of the dataview objects
        instance = self.xform.instances.last()
        # add metadata to instance
        self._add_external_export_metadata(instance)

        params = {"instance": instance.id,
                  "project": self.project.id,
                  "dataview": self.data_view.id}

        request = self.factory.get('/', data=params, **self.extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)
