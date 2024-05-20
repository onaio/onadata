"""Tests for module onadata.libs.models.share_project"""

from unittest.mock import patch, call
from pyxform.builder import create_survey_element_from_dict

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.merged_xform import MergedXForm
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
        self._publish_markdown(md_xform, self.user, project, id_string="a")
        self.dataview_form = XForm.objects.all().order_by("-pk")[0]
        DataView.objects.create(
            name="Demo",
            xform=self.dataview_form,
            project=self.project,
            matches_parent=True,
            columns=[],
        )
        # MergedXForm
        self._publish_markdown(md_xform, self.user, project, id_string="b")
        xf1 = XForm.objects.get(id_string="a")
        xf2 = XForm.objects.get(id_string="b")
        survey = create_survey_element_from_dict(xf1.json_dict())
        survey["id_string"] = "c"
        survey["sms_keyword"] = survey["id_string"]
        survey["title"] = "Merged XForm"
        self.merged_xf = MergedXForm.objects.create(
            id_string=survey["id_string"],
            sms_id_string=survey["id_string"],
            title=survey["title"],
            user=self.user,
            created_by=self.user,
            is_merged_dataset=True,
            project=self.project,
            xml=survey.to_xml(),
            json=survey.to_json(),
        )
        self.merged_xf.xforms.add(xf1)
        self.merged_xf.xforms.add(xf2)
        self.alice = self._create_user("alice", "Yuao8(-)")

    @patch("onadata.libs.models.share_project.safe_delete")
    def test_share(self, mock_safe_delete, mock_propagate):
        """A project is shared with a user

        Permissions assigned to project, xform and dataview
        """
        instance = ShareProject(self.project, self.alice, "manager")
        instance.save()
        self.alice.refresh_from_db()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf.xform_ptr))
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
        ManagerRole.add(self.alice, self.merged_xf)
        ManagerRole.add(self.alice, self.merged_xf.xform_ptr)

        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.merged_xf.xform_ptr))
        # Remove user
        instance = ShareProject(self.project, self.alice, "manager", True)
        instance.save()
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.dataview_form))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.merged_xf))
        mock_propagate.assert_called_once_with(args=[self.project.pk])
        # Cache is invalidated
        mock_safe_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )
