# -*- coding: utf-8 -*-
"""
Test onadata.apps.api.permissions module.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.http import Http404

from onadata.apps.api.permissions import (
    AlternateHasObjectPermissionMixin,
    IsAuthenticatedSubmission,
    MetaDataObjectPermissions,
)
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import Instance, XForm
from onadata.libs.permissions import UserProfile


class TestPermissions(TestAbstractViewSet):
    """
    Test permission classes
    """

    def setUp(self):
        super().setUp()
        self.view = MagicMock()
        self.permissions = MetaDataObjectPermissions()
        self.instance = MagicMock(Instance)
        self.instance.xform = MagicMock(XForm)

    def test_delete_instance_metadata_perms(self):
        request = MagicMock(user=MagicMock(), method="DELETE")
        obj = MagicMock(content_object=self.instance)
        self.assertTrue(self.permissions.has_object_permission(request, self.view, obj))

    @patch.object(AlternateHasObjectPermissionMixin, "_has_object_permission")
    def test_delete_instance_metadata_without_perms(self, has_perms_mock):
        """
        Test that a user cannot delete an instance if they are not allowed
        through the XForm or the Project
        """
        has_perms_mock.return_value = False
        user = User(username="test")
        instance = Instance(user=User(username="username"))
        instance.xform = XForm()
        request = MagicMock(user=user, method="DELETE")
        obj = MagicMock(content_object=instance)
        self.assertFalse(
            self.permissions.has_object_permission(request, self.view, obj)
        )

    def test_is_authenticated_submission_permissions(self):
        """
        Tests that permissions for submissions are applied correctly
        """
        self._publish_xls_form_to_project()
        user = self.xform.user
        project = self.xform.project
        submission_permission = IsAuthenticatedSubmission()

        request = MagicMock(method="GET")
        view = MagicMock(username=user.username)
        self.assertTrue(submission_permission.has_permission(request, self.view))

        request = MagicMock(method="POST")
        view = MagicMock(kwargs={"username": user.username})
        self.assertTrue(submission_permission.has_permission(request, view))

        view = MagicMock(kwargs={"username": "test_user"})
        with self.assertRaises(Http404):
            submission_permission.has_permission(request, view)

        view = MagicMock(kwargs={"xform_pk": self.xform.pk})
        self.assertTrue(submission_permission.has_permission(request, view))

        view = MagicMock(kwargs={"project_pk": project.pk})
        self.assertTrue(submission_permission.has_permission(request, view))

        profile = UserProfile.objects.get(user=user)
        profile.require_auth = True
        profile.save()
        view = MagicMock(kwargs={"username": user.username})
        self.assertFalse(submission_permission.has_permission(request, view))

        view = MagicMock(kwargs={"xform_pk": self.xform.pk})
        self.assertFalse(submission_permission.has_permission(request, view))

        view = MagicMock(kwargs={"project_pk": project.pk})
        self.assertFalse(submission_permission.has_permission(request, view))
