# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.project_utils
"""
from unittest.mock import call, MagicMock, patch

from django.test.utils import override_settings
from kombu.exceptions import OperationalError
from requests import Response
from guardian.shortcuts import get_perms

from onadata.apps.api.models import Team
from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import DataEntryRole, ManagerRole, OwnerRole
from onadata.libs.utils.project_utils import (
    assign_change_asset_permission,
    retrieve_asset_permissions,
    set_project_perms_to_xform,
    set_project_perms_to_xform_async,
    set_project_perms_to_object,
)


class TestProjectUtils(TestBase):
    """
    Test project_utils module.
    """

    def setUp(self):
        super(TestProjectUtils, self).setUp()

        self._create_user("bob", "bob", create_profile=True)

    def test_set_project_perms_to_xform(self):
        """
        Test set_project_perms_to_xform(xform, project)
        """
        self._publish_transportation_form()
        # Alice has data entry role to default project
        alice = self._create_user("alice", "alice", create_profile=True)
        DataEntryRole.add(alice, self.project)
        set_project_perms_to_xform(self.xform, self.project)
        self.assertTrue(DataEntryRole.user_has_role(alice, self.xform))
        self.assertTrue(self.project.pk, self.xform.project_id)

        # Create other project and transfer xform to new project
        project_b = Project(
            name="Project B", created_by=self.user, organization=self.user
        )
        project_b.save()
        self.xform.project = project_b
        self.xform.save()
        self.xform.refresh_from_db()
        self.assertTrue(self.project.pk, self.xform.project_id)

        # set permissions for new project
        set_project_perms_to_xform(self.xform, project_b)

        # Alice should have no data entry role to transfered form
        self.assertFalse(DataEntryRole.user_has_role(alice, self.xform))

    # pylint: disable=invalid-name
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("onadata.libs.utils.project_utils.set_project_perms_to_xform")
    def test_set_project_perms_to_xform_async(self, mock):
        """
        Test that the set_project_perms_to_xform_async task actually calls
        the set_project_perms_to_xform function
        """
        self._publish_transportation_form()
        set_project_perms_to_xform_async.delay(self.xform.pk, self.project.pk)
        self.assertTrue(mock.called)
        args, _kwargs = mock.call_args_list[0]
        self.assertEqual(args[0], self.xform)
        self.assertEqual(args[1], self.project)

    @patch("onadata.libs.utils.project_utils.set_project_perms_to_xform")
    def test_set_project_perms_to_xform_async_mergedxform(self, mock):
        """set_project_perms_to_xform_async sets permissions for a MergedXForm"""
        merged_xf = self._create_merged_dataset()
        set_project_perms_to_xform_async.delay(merged_xf.pk, self.project.pk)
        expected_calls = [
            call(merged_xf.xform_ptr, self.project),
            call(merged_xf, self.project),
        ]
        mock.assert_has_calls(expected_calls, any_order=True)

    def test_assign_change_asset_permission(self):
        """
        Test that the `assign_change_asset_permission` function calls
        the External service with the correct payload
        """
        session_mock = MagicMock()
        asset_id = "some_id"
        usernames = ["bob", "john", "doe"]
        resp = Response()
        resp.status_code = 200
        session_mock.post.return_value = resp

        assign_change_asset_permission(
            "http://example.com", asset_id, usernames, session_mock
        )
        session_mock.post.assert_called()
        session_mock.post.assert_called_with(
            f"http://example.com/api/v2/assets/{asset_id}/permission-assignments/bulk/",
            json=[
                {
                    "user": "http://example.com/api/v2/users/bob/",
                    "permission": "http://example.com/api/v2/permissions/change_asset/",
                },
                {
                    "user": "http://example.com/api/v2/users/john/",
                    "permission": "http://example.com/api/v2/permissions/change_asset/",
                },
                {
                    "user": "http://example.com/api/v2/users/doe/",
                    "permission": "http://example.com/api/v2/permissions/change_asset/",
                },
            ],
        )

    def test_retrieve_asset_permission(self):
        """
        Test that the `retrieve_asset_permissions` function calls
        the External service with the correct payload
        """
        session_mock = MagicMock()
        asset_id = "some_id"
        service_url = "http://example.com"
        resp = Response()
        resp.status_code = 200
        # pylint: disable=protected-access
        resp._content = (
            b'[{"user": "http://example.com/api/v2/users/bob", "url": '
            b'"http://example.com/api/v2/permission-assignments/some_uuid"}]'
        )
        session_mock.get.return_value = resp

        ret = retrieve_asset_permissions(service_url, asset_id, session_mock)
        session_mock.get.assert_called()
        session_mock.get.assert_called_with(
            f"{service_url}/api/v2/assets/{asset_id}/permission-assignments/"
        )
        self.assertEqual(
            ret, {"bob": ["http://example.com/api/v2/permission-assignments/some_uuid"]}
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch(
        "onadata.libs.utils.project_utils.set_project_perms_to_xform_async.delay"  # noqa
    )
    @patch("onadata.libs.utils.project_utils.set_project_perms_to_xform")
    def test_rabbitmq_connection_error(self, mock_set_perms_async, mock_set_perms):
        """
        Test rabbitmq connection error.
        """
        mock_set_perms_async.side_effect = OperationalError("connection error")
        self._publish_transportation_form()
        self.assertFalse(mock_set_perms_async.called)
        self.assertTrue(mock_set_perms.called)


class SetProjectPermsToObjectTestCase(TestBase):
    """Tests for set_project_perms_to_object"""

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self.alice = self._create_user(username="alice", password="abc123!!")
        ManagerRole.add(self.alice, self.project)

    def test_set_perms(self):
        """Project permissions are applied to object"""
        set_project_perms_to_object(self.xform, self.project)

        self.assertTrue(OwnerRole.user_has_role(self.user, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))

    def test_owners_team_permissions(self):
        """Object permissions for owners group are set"""
        team = Team.objects.create(
            name=f"{self.user.username}#Owners", organization=self.user
        )
        self.assertEqual(get_perms(team, self.xform), [])

        set_project_perms_to_object(self.xform, self.project)
        perms = get_perms(team, self.xform)

        self.assertTrue("add_xform" in perms)
        self.assertTrue("view_xform" in perms)
        self.assertTrue("change_xform" in perms)
        self.assertTrue("delete_xform" in perms)

    def test_xform_creator(self):
        """XForm creator is made owner"""
        self.xform.created_by = self.alice
        self.xform.save()

        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

        set_project_perms_to_object(self.xform, self.project)

        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
