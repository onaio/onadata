"""Tests for module onadata.libs.models.share_project"""

from unittest.mock import patch, call

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import ManagerRole


@patch(
    "onadata.libs.models.share_project.propagate_project_permissions_async.apply_async"
)
class ShareProjectTestCase(TestBase):
    """Tests for model ShareProject"""

    def setUp(self):
        super().setUp()

        self._publish_transportation_form()
        self.dataview_form = XForm.objects.all().order_by("-pk")[0]
        DataView.objects.create(
            name="Demo",
            xform=self.dataview_form,
            project=self.project,
            matches_parent=True,
            columns=[],
        )
        self.merged_xf = self._create_merged_dataset()
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)
        self.alice = self._create_user("alice", "Yuao8(-)")

    @patch("onadata.libs.models.share_project.safe_delete")
    def test_share(self, mock_safe_delete, mock_propagate):
        """A project is shared with a user

        Permissions assigned to project, xform, mergedxform and dataview
        """
        instance = ShareProject(self.project, self.alice, "manager")
        instance.save()
        self.alice.refresh_from_db()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf.xform_ptr))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.entity_list))
        mock_propagate.assert_called_once_with(args=[self.project.pk])
        # Cache is invalidated
        mock_safe_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )

    @patch("onadata.libs.models.share_project.safe_delete")
    def test_remove(self, mock_safe_delete, mock_propagate):
        """A user is removed from a project

        Permissions removed from project, xform, mergedxform and dataview
        """
        # Simulate share project
        ManagerRole.add(self.alice, self.project)
        ManagerRole.add(self.alice, self.xform)
        ManagerRole.add(self.alice, self.dataview_form)
        ManagerRole.add(self.alice, self.merged_xf)
        ManagerRole.add(self.alice, self.merged_xf.xform_ptr)
        ManagerRole.add(self.alice, self.entity_list)
        # Confirm project shared
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf.xform_ptr))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.entity_list))
        # Remove user
        instance = ShareProject(self.project, self.alice, "manager", True)
        instance.save()
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.merged_xf))
        self.assertFalse(
            ManagerRole.user_has_role(self.alice, self.merged_xf.xform_ptr)
        )
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.entity_list))
        mock_propagate.assert_called_once_with(args=[self.project.pk])
        # Cache is invalidated
        mock_safe_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )
