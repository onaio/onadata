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
            'username': 'joe,%(user)s,jake' % {
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
            'username': 'dave,jake',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(ReadOnlyRole.user_has_role(user_dave, project))
        self.assertTrue(ReadOnlyRole.user_has_role(user_jake, project))

        # Test strips spaces between commas
        user_sam = self._create_user('sam', 'sam')
        user_joy = self._create_user('joy', 'joy')

        self.assertFalse(ReadOnlyRole.user_has_role(user_sam, project))
        self.assertFalse(ReadOnlyRole.user_has_role(user_joy, project))

        data = {
            'project': project.id,
            'username': 'sam, joy',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(ReadOnlyRole.user_has_role(user_sam, project))
        self.assertTrue(ReadOnlyRole.user_has_role(user_joy, project))

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
                         "The following user(s) does/do not exist: doe")

        data = {
            'project': project.id,
            'username': 'doe,john',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors['username'][0]),
                         "The following user(s) does/do not exist: doe, john")

    def test_error_on_inactive_user(self):
        """
        Test that an error is raised when user(s) passed does not
        exist
        """

        self._publish_xls_form_to_project()

        project = Project.objects.last()
        user_dave = self._create_user('dave', 'dave')
        user_dave.is_active = False
        user_dave.save()

        data = {
            'project': project.id,
            'username': 'dave',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors['username'][0]),
                         "The following user(s) is/are not active: dave")

        user_john = self._create_user('john', 'john')
        user_john.is_active = False
        user_john.save()

        data = {
            'project': project.id,
            'username': 'dave,john',
            'role': ReadOnlyRole.name
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(str(serializer.errors['username'][0]),
                         "The following user(s) is/are not active: dave, john")
