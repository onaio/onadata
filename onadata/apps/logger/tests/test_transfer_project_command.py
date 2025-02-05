"""Tests for project transfer command"""

import os
import sys

from django.core.management import call_command

from six import StringIO

from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.tests.test_base import TestBase


class TestMoveProjectToAnewOwner(TestBase):  # pylint: disable=C0111
    def setUp(self):
        super().setUp()

        self.from_user = self._create_user("bob", "test_pass")
        self.alice = self._create_user("alice", "test_pass")
        org = self._create_organization("alice_inc", "Alice Inc", self.alice)
        self.to_user = org.user
        Project.objects.bulk_create(
            [
                Project(
                    name=f"Test_project_{i}",
                    organization=self.from_user,
                    created_by=self.from_user,
                )
                for i in range(1, 6)
            ]
        )

    def test_transfer_all(self):  # pylint: disable=C0103
        """Transfer all projects from one user to another."""
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        call_command(
            "transferproject",
            current_owner=self.from_user.username,
            new_owner=self.to_user.username,
            all_projects=True,
            stdout=mock_stdout,
        )
        expected_output = "Projects transferred successfully"
        self.assertIn(expected_output, mock_stdout.getvalue())
        self.assertEqual(0, Project.objects.filter(organization=self.from_user).count())
        self.assertEqual(5, Project.objects.filter(organization=self.to_user).count())

    def test_transfer_one(self):
        """Transfer a single project from one user to another."""
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        target_project = Project.objects.filter(organization=self.from_user).first()
        call_command(
            "transferproject",
            current_owner=self.from_user.username,
            new_owner=self.to_user.username,
            project_id=target_project.id,
        )
        expected_output = "Projects transferred successfully"
        self.assertIn(expected_output, mock_stdout.getvalue())
        self.assertEqual(4, Project.objects.filter(organization=self.from_user).count())
        self.assertEqual(1, Project.objects.filter(organization=self.to_user).count())

    def test_xforms_are_transferred_as_well(self):  # pylint: disable=C0103
        """Test the transfer of ownership of the XForms."""
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        call_command(
            "transferproject",
            current_owner=self.from_user,
            new_owner=self.to_user,
            all_projects=True,
            stdout=mock_stdout,
        )
        self.assertIn("Projects transferred successfully\n", mock_stdout.getvalue())
        bobs_forms = XForm.objects.filter(user=self.from_user)
        new_owner_forms = XForm.objects.filter(user=self.to_user)
        self.assertEqual(0, bobs_forms.count())
        self.assertEqual(1, new_owner_forms.count())


class TestUserValidation(TestBase):
    """Created this class to specifically test for the user validation.

    When the function is put together with the other test functions above,
    it's stdout is interfering with the other functions causing them to fail.
    stdout.flush() does not help.
    """

    def test_user_given_does_not_exist(self):  # pylint: disable=C0103
        """Test that users are validated before initiating project transfer"""
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        call_command(
            "transferproject",
            current_owner="user1",
            new_owner="user2",
            all_projects=True,
        )
        expected_output = "User user1 does not existUser user2 does " "not exist\n"
        self.assertEqual(mock_stdout.getvalue(), expected_output)
