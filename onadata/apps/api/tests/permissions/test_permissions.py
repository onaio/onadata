from django.contrib.auth.models import User
from mock import MagicMock, patch
from onadata.apps.main.tests.test_base import TestBase

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.api.permissions import (
    MetaDataObjectPermissions,
    AlternateHasObjectPermissionMixin
)


class TestPermissions(TestBase):
    def setUp(self):
        self.view = MagicMock()
        self.permissions = MetaDataObjectPermissions()
        self.instance = MagicMock(Instance)
        self.instance.xform = MagicMock(XForm)

    def test_delete_instance_metadata_perms(self):
        request = MagicMock(user=MagicMock(), method='DELETE')
        obj = MagicMock(content_object=self.instance)
        self.assertTrue(
            self.permissions.has_object_permission(
                request, self.view, obj))

    @patch.object(AlternateHasObjectPermissionMixin, '_has_object_permission')
    def test_delete_instance_metadata_without_perms(self, has_perms_mock):
        """
        Test that a user cannot delete an instance if they are not allowed
        through the XForm or the Project
        """
        has_perms_mock.return_value = False
        user = User(username="test")
        instance = Instance(user=User(username="username"))
        instance.xform = XForm()
        request = MagicMock(user=user, method='DELETE')
        obj = MagicMock(content_object=instance)
        self.assertFalse(
            self.permissions.has_object_permission(
                request, self.view, obj))
