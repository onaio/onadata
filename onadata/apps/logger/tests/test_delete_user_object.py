"""Tests for project transfer command"""
import os
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils.six import StringIO

from onadata.apps.main.tests.test_base import TestBase


class TestDeleteUserObjectsCommand(TestBase):  # pylint: disable=C0111
    def setUp(self, *args, **kwargs):
        self.out = StringIO()
        sys.stdout = self.out
        super(TestDeleteUserObjectsCommand, self).setUp(*args, **kwargs)

    def test_user_does_not_exist(self):
        call_command(
            'delete_user_object', username='test', object_type='xform',
            unique_field='title', unique_field_value='test',
            stdout=self.out
        )
        expected_output = 'User with username test does not exist\n'
        self.assertIn(expected_output, self.out.getvalue())

    def test_delete_xform_does_not_exist(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username='test', email='test@test.com', password='test')
        call_command(
            'delete_user_object', username='test', object_type='xform',
            unique_field='title', unique_field_value='test',
            stdout=self.out
        )
        expected_output = 'xform with title test does not exist\n'
        self.assertIn(expected_output, self.out.getvalue())

    def test_invalid_object_type(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username='test', email='test@test.com', password='test')
        call_command(
            'delete_user_object', username='test', object_type='some_object',
            unique_field='title', unique_field_value='test',
            stdout=self.out
        )
        expected_output = 'some_object is not a valid object_type\n'
        self.assertIn(expected_output, self.out.getvalue())

    def test_delete_xform(self):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT,
            'apps/main/tests/',
            "fixtures/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        call_command(
            'delete_user_object', username='bob', object_type='xform',
            unique_field='title', unique_field_value='tutorial',
            stdout=self.out
        )
        expected_output = 'bob deleted successfully.\n'
        self.assertIn(expected_output, self.out.getvalue())

    def test_delete_project_does_not_exist(self):
        xls_file_path = os.path.join(
            settings.PROJECT_ROOT,
            'apps/main/tests/',
            "fixtures/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        call_command(
            'delete_user_object', username='bob', object_type='project',
            unique_field='name', unique_field_value='tutorial',
            stdout=self.out
        )
        expected_output = 'project with name tutorial does not exist\n'
        self.assertIn(expected_output, self.out.getvalue())
