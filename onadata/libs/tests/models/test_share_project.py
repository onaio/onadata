"""Tests for module onadata.libs.models.share_project"""

from unittest.mock import patch, call

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.project import Project
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
        md_xform = """
        | survey  |
        |         | type              | name  | label  |
        |         | text              | name  | Name   |
        |         | integer           | age   | Age    |
        |         | select one fruits | fruit | Fruit  |
        |         |                   |       |        |
        | choices | list name         | name  | label  |
        |         | fruits            | 1     | Mango  |
        |         | fruits            | 2     | Orange |
        |         | fruits            | 3     | Apple  |
        """
        project = Project.objects.create(
            name="Demo", organization=self.user, created_by=self.user
        )
        self._publish_markdown(md_xform, self.user, project)
        self.dataview_form = XForm.objects.all().order_by("-pk")[0]
        DataView.objects.create(
            name="Demo",
            xform=self.dataview_form,
            project=self.project,
            matches_parent=True,
            columns=[],
        )
        self.alice = self._create_user("alice", "Yuao8(-)")

    @patch("onadata.libs.models.share_project.safe_delete")
    def test_share(self, mock_safe_delete, mock_propagate):
        """A project is shared with a user

        Permissions assigned to project, xform and dataview
        """
        instance = ShareProject(self.project, self.alice, "manager")
        instance.save()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
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
        """A user is removed from a project"""
        # Add user
        ManagerRole.add(self.alice, self.project)
        ManagerRole.add(self.alice, self.xform)
        ManagerRole.add(self.alice, self.dataview_form)

        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        # Remove user
        instance = ShareProject(self.project, self.alice, "manager", True)
        instance.save()
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.dataview_form))
        mock_propagate.assert_called_once_with(args=[self.project.pk])
        # Cache is invalidated
        mock_safe_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )
