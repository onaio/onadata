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
            'role': 'readonly'
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors['username'][0]),
            "Cannot share project with the owner (%(value)s)" %
            {"value": self.user.username})

        # Test that this fails even when multiple users are passed
        user_joe = self._create_user('joe', 'joe')
        user_jake = self._create_user('jake', 'jake')

        data = {
            'project': project.id,
            'usernames': '%(user_a)s,%(user_b)s,%(user_c)s' % {
                "user_a": user_joe.username,
                "user_b": self.user.username,
                "user_c": user_jake.username,
            },
            'role': 'readonly'
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

        self.assertFalse(user_joe.has_perm('view_project', obj=project))

        data = {
            'project': project.id,
            'username': user_joe.username,
            'role': 'readonly'
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(user_joe.has_perm('view_project', obj=project))

        # Test that it can share to multiple users
        user_dave = self._create_user('dave', 'dave')
        user_jake = self._create_user('jake', 'jake')

        self.assertFalse(user_dave.has_perm('view_project', obj=project))
        self.assertFalse(user_jake.has_perm('view_project', obj=project))

        data = {
            'project': project.id,
            'usernames': '%(user_a)s,%(user_b)s' % {
                "user_a": user_dave.username,
                "user_b": user_jake.username
            },
            'role': 'readonly'
        }

        serializer = ShareProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertTrue(user_dave.has_perm('view_project', obj=project))
        self.assertTrue(user_jake.has_perm('view_project', obj=project))
