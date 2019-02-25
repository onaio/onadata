import sys

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils.six import StringIO

from onadata.apps.logger.models import Project


class TestMoveProjectTonewOwner(TestCase):
    def test_user_given_does_not_exist(self):
        out = StringIO()
        sys.stdout = out
        call_command(
            'reassign_project_owners', currentowner='user1',
            newowner='user2', stdout=out
        )
        expected_output = 'User user1 does not exist \nUser user2 '\
                          'does not exist \n'
        self.assertIn(expected_output, out.getvalue())

    def test_successful_projects_reassignment(self):
        um = get_user_model()
        user1 = um.objects.create_user(
            username='user1', email='user1@test.com', password='test_pass')
        user2 = um.objects.create_user(
            username='user2', email='user2@test.com', password='test_pass')
        Project.objects.create(
            name='Test_project_1', organization=user1, created_by=user1)
        Project.objects.create(
            name='Test_project_2', organization=user1, created_by=user1)
        Project.objects.create(
            name='Test_project_3', organization=user1, created_by=user1)
        Project.objects.create(
            name='Test_project_4', organization=user1, created_by=user1)
        Project.objects.create(
            name='Test_project_5', organization=user1, created_by=user1)
        out = StringIO()
        sys.stdout = out
        call_command(
            'reassign_project_owners', currentowner='user1',
            newowner='user2', stdout=out
        )
        expected_output = 'Projects reassigned successfully'
        self.assertIn(expected_output, out.getvalue())
        self.assertEquals(
            0, Project.objects.filter(organization=user1).count()
        )
        self.assertEquals(
            5, Project.objects.filter(organization=user2).count()
        )
