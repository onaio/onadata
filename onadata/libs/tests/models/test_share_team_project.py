"""Tests for module onadata.libs.models.share_team_project"""

from unittest.mock import call, patch

from onadata.apps.api.models import Team
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import ManagerRole


class ShareTeamProjectTestCase(TestBase):
    """Tests for model ShareTeamProject"""

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
        self.team = Team.objects.create(
            name=f"{self.user.username}#test_team",
            organization=self.user,
        )
        self.alice = self._create_user("alice", "Yuao8(-)")
        add_user_to_team(self.team, self.alice)

    @patch("onadata.libs.models.share_team_project.safe_cache_delete")
    def test_share(self, mock_safe_cache_delete):
        """Sharing a project with a team assigns permissions and clears cache"""
        instance = ShareTeamProject(self.team, self.project, "manager")
        instance.save()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        # Cache is invalidated
        mock_safe_cache_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )

    @patch("onadata.libs.models.share_team_project.safe_cache_delete")
    def test_remove(self, mock_safe_cache_delete):
        """Removing a team from a project removes permissions and clears cache"""
        # Simulate share project
        ManagerRole.add(self.team, self.project)
        ManagerRole.add(self.team, self.xform)
        ManagerRole.add(self.team, self.dataview_form)
        # Confirm project shared
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.dataview_form))
        # Remove team
        instance = ShareTeamProject(self.team, self.project, "manager", remove=True)
        instance.save()
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.dataview_form))
        # Cache is invalidated
        mock_safe_cache_delete.assert_has_calls(
            [
                call(f"ps-project_owner-{self.project.pk}"),
                call(f"ps-project_permissions-{self.project.pk}"),
            ]
        )
