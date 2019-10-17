"""
Test ShareProjectSerializer module
"""
from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.share_project_serializer import (
    ShareProjectSerializer)
from onadata.libs.permissions import ReadOnlyRole


class TestShareProjectSerializer(TestAbstractViewSet, TestBase):
    """
    TestShareProjectSerializer class
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    def test_error_on_share_to_owner(self):
        """
        Test that a validation error is raised when
        trying to share a project to the owner
        """

        self._publish_xls_form_to_project()

        project = Project.objects.last()

        data = {
            'project': project.id,
            'username': self.user.username,
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['username'][0]),
            "Cannot share project with the owner (%(value)s)" %
            {"value": self.user.username})

        # Test that this fails even when multiple users are passed
        self._create_user('joe', 'joe')
        self._create_user('jake', 'jake')

        data = {
            'project': project.id,
            'usernames': 'joe,%(user)s,jake' % {
                "user": self.user.username,
            },
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['username'][0]),
            "Cannot share project with the owner (%(value)s)" %
            {"value": self.user.username})

    def test_shares_project(self):
        """
        Test that the ShareProjectSerializer shares the projects to users
        """
        self._publish_xls_form_to_project()
        project = Project.objects.last()

        user_joe = self._create_user('joe', 'joe')

        self.assertFalse(ReadOnlyRole.user_has_role(user_joe, project))

        data = {
            'project': project.id,
            'username': 'joe',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(ReadOnlyRole.user_has_role(user_joe, project))

        # Test that it can share to multiple users
        user_dave = self._create_user('dave', 'dave')
        user_jake = self._create_user('jake', 'jake')

        self.assertFalse(ReadOnlyRole.user_has_role(user_dave, project))
        self.assertFalse(ReadOnlyRole.user_has_role(user_jake, project))

        data = {
            'project': project.id,
            'usernames': 'dave,jake',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(ReadOnlyRole.user_has_role(user_dave, project))
        self.assertTrue(ReadOnlyRole.user_has_role(user_jake, project))

    def test_error_on_username_and_usernames_missing(self):
        """
        Test that an error is raised when both "username" and "usernames"
        field are missing
        """
        self._publish_xls_form_to_project()

        project = Project.objects.last()

        data = {'project': project.id, 'role': ReadOnlyRole.name}

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['username'][0]),
            "Either username or usernames field should be present")
        self.assertEqual(
            str(serializer.errors['usernames'][0]),
            "Either username or usernames field should be present")

    def test_error_on_non_existing_user(self):
        """
        Test that an error is raised when user(s) passed does not
        exist
        """

        self._publish_xls_form_to_project()

        project = Project.objects.last()

        data = {
            'project': project.id,
            'username': 'doe',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors['username'][0]),
                         "User 'doe' does not exist.")

        data = {
            'project': project.id,
            'usernames': 'doe,john',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors['usernames'][0]),
                         "The following users do not exist: 'doe, john'")
