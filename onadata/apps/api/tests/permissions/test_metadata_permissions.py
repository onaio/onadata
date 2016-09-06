import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet


class TestMetaDataObjectPermissions(TestAbstractViewSet):

    def setUp(self):
        super(TestMetaDataObjectPermissions, self).setUp()
        self.view = MetaDataViewSet.as_view({
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

        ContentType.objects.get_or_create(app_label="logger", model="instance")

    def test_form_admin_can_delete_metadata(self):
        """User with form delete permissions can delete submission metadata"""
        metadata_permission = MetaDataObjectPermissions()
        self._add_instance_metadata(
            'supporting_doc', self.data_value, self.path)

        request = self.factory.delete('/', **self.extra)
        request.user = self.user

        has_delete_instance_perms = metadata_permission.has_object_permission(
            request, self.view, self.metadata)

        self.assertTrue(has_delete_instance_perms)

    def test_non_admin_cannot_delete_metadata(self):
        """
        User without form delete permissions cannot delete submission metadata
        """
        metadata_permission = MetaDataObjectPermissions()
        self._add_instance_metadata(
            'supporting_doc', self.data_value, self.path)

        self._login_user_and_profile({'username': 'bla',
                                      'email': 'bla@email.com'})
        request = self.factory.delete('/', **self.extra)
        request.user = self.user

        has_delete_instance_perms = metadata_permission.has_object_permission(
            request, self.view, self.metadata)

        self.assertFalse(has_delete_instance_perms)
