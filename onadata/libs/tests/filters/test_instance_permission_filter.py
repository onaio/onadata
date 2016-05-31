from django.contrib.contenttypes.models import ContentType

from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Project
from onadata.apps.main.models.meta_data import MetaData


class TestMetaDataFilter(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._create_user_and_login()

        self._publish_transportation_form_and_submit_instance()

        content_object = self.xform.instances.first()
        self._add_external_export_metadata(content_object)

        self.view = MetaDataViewSet.as_view({'get': 'list'})

        ContentType.objects.get_or_create(app_label="logger", model="instance")

    def _add_external_export_metadata(self, content_object):
        MetaData.external_export(content_object,
                                 "https://test/external/export")

    def test_metadata_filter_for_user_with_xform_perms(self):
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        project = Project.objects.create(name="Test Project",
                                         organization=self.user,
                                         created_by=self.user)
        self.xform.project = project
        self.xform.save()

        instance = self.xform.instances.first()

        params = {"instance": instance.id,
                  "project": project.id,
                  "xform": self.xform.id}
        request = self.factory.get('/', data=params, **extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 1)

    def test_metadata_filter_for_user_without_xform_perms(self):
        self._create_user_and_login("alice", "password")
        extra = {'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        instance = self.xform.instances.first()

        params = {"instance": instance.id,
                  "xform": self.xform.id}
        request = self.factory.get('/', data=params, **extra)
        response = self.view(request)

        self.assertEquals(len(response.data), 0)
