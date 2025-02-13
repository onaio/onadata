"""Tests for project transfer command"""

import os
import sys

from django.contrib.auth import get_user_model
from django.core.management import call_command

from six import StringIO

from onadata.apps.api.models import Team
from onadata.apps.logger.models import Project, XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import OwnerRole, ReadOnlyRole


class TestMoveProjectToAnewOwner(TestBase):  # pylint: disable=C0111
    def test_successful_project_transfer(self):  # pylint: disable=C0103
        """ "Test for a successful project transfer."""
        user_model = get_user_model()
        user_1_data = {
            "username": "user1",
            "email": "user1@test.com",
            "password": "test_pass",
        }
        user_2_data = {
            "username": "user2",
            "email": "user2@test.com",
            "password": "test_pass",
        }
        user1 = user_model.objects.create_user(**user_1_data)
        user2 = user_model.objects.create_user(**user_2_data)
        Project.objects.create(
            name="Test_project_1", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_2", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_3", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_4", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_5", organization=user1, created_by=user1
        )
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        call_command(
            "transferproject",
            current_owner="user1",
            new_owner="user2",
            all_projects=True,
            stdout=mock_stdout,
        )
        expected_output = "Projects transferred successfully"
        self.assertIn(expected_output, mock_stdout.getvalue())
        self.assertEqual(0, Project.objects.filter(organization=user1).count())
        self.assertEqual(5, Project.objects.filter(organization=user2).count())

    def test_single_project_transfer(self):
        """ "Test for a successful project transfer."""
        user_model = get_user_model()
        user_1_data = {
            "username": "user1",
            "email": "user1@test.com",
            "password": "test_pass",
        }
        user_2_data = {
            "username": "user2",
            "email": "user2@test.com",
            "password": "test_pass",
        }
        user1 = user_model.objects.create_user(**user_1_data)
        user2 = user_model.objects.create_user(**user_2_data)
        Project.objects.create(
            name="Test_project_1", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_2", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_3", organization=user1, created_by=user1
        )
        Project.objects.create(
            name="Test_project_4", organization=user1, created_by=user1
        )

        test_project = Project.objects.create(
            name="Test_project_5", organization=user1, created_by=user1
        )
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        self.assertIsNotNone(test_project.id)

        call_command(
            "transferproject",
            current_owner="user1",
            new_owner="user2",
            project_id=test_project.id,
        )
        expected_output = "Projects transferred successfully"
        self.assertIn(expected_output, mock_stdout.getvalue())
        self.assertEqual(4, Project.objects.filter(organization=user1).count())
        self.assertEqual(1, Project.objects.filter(organization=user2).count())
        test_project_refetched = Project.objects.get(id=test_project.id)
        self.assertEqual(user2, test_project_refetched.organization)

    def test_xforms_are_transferred_as_well(self):  # pylint: disable=C0103
        """Test the transfer of ownership of the XForms."""
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xlsx",
        )
        self._publish_xls_file_and_set_xform(xls_file_path)
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/instances/tutorial_2012-06-27_11-27-53.xml",
        )

        self._make_submission(xml_submission_file_path)
        self.assertEqual(self.response.status_code, 201)

        user_model = get_user_model()
        user_data = {
            "username": "user",
            "email": "user@test.com",
            "password": "test_pass",
        }
        new_owner = user_model.objects.create_user(**user_data)
        mock_stdout = StringIO()
        sys.stdout = mock_stdout
        call_command(
            "transferproject",
            current_owner="bob",
            new_owner="user",
            all_projects=True,
            stdout=mock_stdout,
        )
        self.assertIn("Projects transferred successfully\n", mock_stdout.getvalue())
        bob = user_model.objects.get(username="bob")
        bobs_forms = XForm.objects.filter(user=bob)
        new_owner_forms = XForm.objects.filter(user=new_owner)
        self.assertEqual(0, bobs_forms.count())
        self.assertEqual(1, new_owner_forms.count())

    def test_transfer_to_org(self):
        """Transferring to an organization works"""
        # Create users
        bob = self._create_user("bob", "test_pass")
        alice = self._create_user("alice", "test_pass")
        jane = self._create_user("jane", "test_pass")
        # Create Project owned by Bob and publish form
        project = Project.objects.create(
            name="Test_project",
            organization=bob,
            created_by=bob,
        )
        self.project = project
        self._publish_transportation_form()
        # Create organization owned by Alice
        alice_org = self._create_organization("alice_inc", "Alice Inc", alice)
        owners_team, _ = Team.objects.get_or_create(
            name=f"{alice_org.user.username}#Owners",
            organization=alice_org.user,
        )
        members_team, _ = Team.objects.get_or_create(
            name=f"{alice_org.user.username}#members",
            organization=alice_org.user,
        )
        # Add Bob as admin to Alice's organization
        bob.groups.add(owners_team)
        bob.groups.add(members_team)
        # Add Jane as member to Alice's organization
        jane.groups.add(members_team)
        # Transfer Bob's project to Alice's organization
        call_command(
            "transferproject",
            current_owner=bob.username,
            new_owner=alice_org.user.username,
            project_id=project.id,
        )
        self.xform.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(self.project.organization, alice_org.user)
        self.assertEqual(self.project.organization, alice_org.user)
        self.assertEqual(self.xform.user, alice_org.user)
        self.assertEqual(self.xform.created_by, alice_org.user)
        # Admins have owner privileges
        self.assertTrue(OwnerRole.user_has_role(bob, project))
        self.assertTrue(OwnerRole.user_has_role(bob, self.xform))
        self.assertTrue(OwnerRole.user_has_role(alice, project))
        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))
        # Non-admins have readonly privileges
        self.assertFalse(OwnerRole.user_has_role(jane, project))
        self.assertTrue(ReadOnlyRole.user_has_role(jane, project))
        self.assertTrue(ReadOnlyRole.user_has_role(jane, self.xform))


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
