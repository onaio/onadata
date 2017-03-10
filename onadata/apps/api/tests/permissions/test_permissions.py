from django.contrib.auth.models import User
from mock import MagicMock
from onadata.apps.main.tests.test_base import TestBase

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.api.permissions import MetaDataObjectPermissions


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

    def test_delete_instance_metadata_without_perms(self):
        user = User(username="test")
        instance = Instance()
        instance.xform = XForm()
        # user.has_perms.return_value = False
        request = MagicMock(user=user, method='DELETE')
        obj = MagicMock(content_object=instance)
        self.assertFalse(
            self.permissions.has_object_permission(
                request, self.view, obj))
