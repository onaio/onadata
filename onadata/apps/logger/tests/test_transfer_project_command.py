"""Tests for project transfer command"""
import os
import sys

from django.contrib.auth import get_user_model
from django.core.management import call_command

from django.utils.six import StringIO

from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase


class TestMoveProjectTonewOwner(TestBase):  # pylint: disable=C0111
    def test_user_given_does_not_exist(self):
        """Test that users are validated before initiating project transfer"""
        out = StringIO()
        sys.stdout = out
        call_command(
            'transfer_project', currentowner='user1', newowner='user2',
            httphost='test_server.com', httpprotocol='https', stdout=out
        )
        expected_output = 'User user1 does not exist \nUser user2 '\
                          'does not exist \n'
        self.assertIn(expected_output, out.getvalue())

    def test_successful_projects_reassignment(self):
        """"Test for a successful project transfer."""
        user_model = get_user_model()
        user_1_data = {
            'username': 'user1',
            'email': 'user1@test.com',
            'password': 'test_pass'
        }
        user_2_data = {
            'username': 'user2',
            'email': 'user2@test.com',
            'password': 'test_pass'
        }
        user1 = user_model.objects.create_user(**user_1_data)
        user2 = user_model.objects.create_user(**user_2_data)
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
            'transfer_project', currentowner='user1', newowner='user2',
            httphost='test_server.com', httpprotocol='https', stdout=out
        )
        expected_output = 'Projects transferred successfully'
        self.assertIn(expected_output, out.getvalue())
        self.assertEquals(
            0, Project.objects.filter(organization=user1).count()
        )
        self.assertEquals(
            5, Project.objects.filter(organization=user2).count()
        )

    def test_transfer_projects_with_xforms(self):
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml"
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)

        xform = XForm.objects.all()[0]
        old_value = "https://dmfrm.enketo.org/webform"
        MetaData.objects.create(
            data_type='enketo_url',
            data_value=old_value,
            object_id=xform.id,
            content_object=xform
        )
        user_model = get_user_model()
        user_2_data = {
            'username': 'user2',
            'email': 'user2@test.com',
            'password': 'test_pass'
        }
        user_model.objects.create_user(**user_2_data)
        call_command(
            'transfer_project', currentowner='bob', newowner='user2',
            httphost='test_server.com', httpprotocol='https')
        self.assertNotEqual(
            old_value, MetaData.objects.get(data_type='enketo_url').data_value)
