# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on moving a form whose meta permissions can make
the destination project's users its admins.
"""

from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.tests.viewsets.test_stepup_form_and_transfer_gates import (
    GateTestCase,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_OWNER,
    gating,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.permissions import EditorRole, ManagerRole, OwnerRole
from onadata.libs.stepup.policy import GATE_SHARE_FORM_ADMIN, GATE_TRANSFER_PROJECT


@gating(GATE_SHARE_FORM_ADMIN)
class TestMoveFormWithAdminMetaPermsGate(GateTestCase):
    """A move gives the form the new project's roles and then applies its
    meta permissions, so an editor of that project can become the form's
    owner."""

    audience = GATE_SHARE_FORM_ADMIN

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.first_project = self.project
        self._project_create({"name": "second"})
        self.second_project = self.project
        self.assertEqual(self.second_project.organization, self.xform.user)
        self.alice = self._create_user("alice", "alice", create_profile=True)
        EditorRole.add(self.alice, self.second_project)

    def _move(self, headers=None):
        view = ProjectViewSet.as_view({"post": "forms"})
        request = self.factory.post(
            "/",
            data={"formid": self.xform.pk},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.second_project.pk)

    def _move_alice_into_an_org_project(self):
        """Make the move's destination a project of another account, which
        alice edits."""
        self._org_create()
        org_url = f"http://testserver/api/v1/users/{self.organization.user.username}"
        self._project_create({"name": "org", "owner": org_url})
        self.second_project = self.project
        self.assertNotEqual(self.second_project.organization, self.xform.user)
        EditorRole.add(self.alice, self.second_project)

    def _project_of_the_form(self):
        self.xform.refresh_from_db()
        return self.xform.project

    def test_a_move_that_makes_an_editor_owner_is_challenged(self):
        """The 401 names the audience and the form stays where it was."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)

        response = self._move()

        self.assert_challenged(response)
        self.assertEqual(self._project_of_the_form(), self.first_project)

    def test_a_grant_lets_the_form_move(self):
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        grant = self._grant()

        response = self._move(self._with_grant(grant))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.second_project)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
        self.assert_spent(grant)

    def test_the_default_meta_perms_are_not_challenged(self):
        """The default meta permissions leave the project's editors
        editors."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self.assert_challenged(self._move())
        self._set_meta_perms("editor|dataentry|readonly")

        response = self._move()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.second_project)

    def test_a_project_admin_is_not_counted(self):
        """A manager of the project already manages every form moved into
        it, so the meta permissions appoint nobody new."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self.assert_challenged(self._move())
        ManagerRole.add(self.alice, self.second_project)

        response = self._move()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.second_project)

    def test_a_move_to_another_account_is_challenged_where_only_this_is_gated(self):
        """Without a transfer gate to cover it, a move into another account
        that makes an editor there the form's owner is challenged as well."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self._move_alice_into_an_org_project()

        response = self._move()

        self.assert_challenged(response)
        self.assertEqual(self._project_of_the_form(), self.first_project)

    @gating(GATE_TRANSFER_PROJECT, GATE_SHARE_FORM_ADMIN)
    def test_a_transfer_grant_covers_the_admins_a_move_appoints(self):
        """Where transfers are gated, a move into another account asks for
        the transfer grant alone rather than refusing two gated changes."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self._move_alice_into_an_org_project()

        response = self._move()

        self.assertEqual(response.status_code, 401, response.data)
        self.assertEqual(response.data["audience"], GATE_TRANSFER_PROJECT)
        self.assertEqual(self._project_of_the_form(), self.first_project)

    @gating(GATE_TRANSFER_PROJECT, GATE_SHARE_FORM_ADMIN)
    def test_the_transfer_grant_alone_lets_the_move_through(self):
        """With the transfer grant the form moves and its meta permissions
        make alice its owner."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self._move_alice_into_an_org_project()
        grant = issue_grant(self.user.pk, GATE_TRANSFER_PROJECT)

        response = self._move({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.second_project)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
        self.assertFalse(spend_grant(self.user.pk, GATE_TRANSFER_PROJECT, grant))
