# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on sharing forms and projects with an admin role
and on making their data public.

Every test that expects a request through first shows that the gate is
active, so removing the gate fails it too.
"""

import json
from unittest.mock import patch

from django.test.utils import override_settings

from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.v2.project_viewset import (
    ProjectViewSet as ProjectViewSetV2,
)
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Project, ProjectInvitation, XForm
from onadata.libs.models.share_project import ShareProject
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorRole, ManagerRole, OwnerRole
from onadata.libs.stepup.policy import (
    GATE_INVITE_PROJECT_ADMIN,
    GATE_PUBLISH_DATA,
    GATE_SHARE_FORM_ADMIN,
    GATE_SHARE_PROJECT_ADMIN,
)


def gating(audience, **settings):
    """Gate ``audience`` alone, for a user with a confirmed factor."""
    return override_settings(
        STEP_UP={
            "MODE": "local",
            "ACTIONS": [audience],
            "NO_FACTOR_POLICY": "skip_gate",
        },
        **settings,
    )


class StepUpGateTestCase(TestAbstractViewSet):
    """Gives ``self.user`` a second factor, without which ``skip_gate`` would
    let every request through ungated."""

    audience = None

    def setUp(self):
        super().setUp()
        # pylint: disable=import-outside-toplevel
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

    def _grant(self):
        return issue_grant(self.user.pk, self.audience)

    def _with_grant(self, grant):
        return {"HTTP_X_STEP_UP_GRANT": grant}

    def assert_challenged(self, response):
        """Refused with a challenge naming this test case's audience."""
        self.assertEqual(response.status_code, 401, response.data)
        self.assertEqual(response.data["audience"], self.audience)

    def assert_spent(self, grant):
        """The gate consumed ``grant``, so the request went through it."""
        self.assertFalse(spend_grant(self.user.pk, self.audience, grant))

    def _user(self, username):
        return self._create_user_profile(
            {"username": username, "email": f"{username}@localhost.com"}
        ).user


@gating(GATE_SHARE_PROJECT_ADMIN)
class TestShareProjectAdminGate(StepUpGateTestCase):
    """An owner or manager of a project can share it on and delete it, so a
    stolen session must not be able to appoint one."""

    audience = GATE_SHARE_PROJECT_ADMIN

    def setUp(self):
        super().setUp()
        self._project_create()
        self.alice = self._user("alice")
        self.tom = self._user("tom")

    def _share(self, username, role, headers=None, **extra_data):
        view = ProjectViewSet.as_view({"put": "share"})
        request = self.factory.put(
            "/",
            data={"username": username, "role": role, **extra_data},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.project.pk)

    def test_sharing_as_owner_is_challenged(self):
        response = self._share("alice", OwnerRole.name)

        self.assert_challenged(response)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.project))

    def test_sharing_as_manager_is_challenged(self):
        response = self._share("alice", ManagerRole.name)

        self.assert_challenged(response)
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_a_grant_lets_the_share_through(self):
        grant = self._grant()

        response = self._share("alice", ManagerRole.name, self._with_grant(grant))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assert_spent(grant)

    def test_one_new_admin_among_several_users_is_challenged(self):
        ShareProject(self.project, "alice", OwnerRole.name).save()
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.project))

        response = self._share("alice,tom", OwnerRole.name)

        self.assert_challenged(response)
        self.assertFalse(OwnerRole.user_has_role(self.tom, self.project))

    def test_a_non_admin_role_is_not_challenged(self):
        self.assert_challenged(self._share("tom", ManagerRole.name))

        response = self._share("alice", EditorRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))

    def test_a_role_every_target_already_holds_is_not_challenged(self):
        ShareProject(self.project, "alice", ManagerRole.name).save()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assert_challenged(self._share("tom", ManagerRole.name))

        response = self._share("alice", ManagerRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))

    def test_removing_an_admin_is_not_challenged(self):
        ShareProject(self.project, "alice", OwnerRole.name).save()
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.project))
        self.assert_challenged(self._share("tom", OwnerRole.name))

        response = self._share("alice", OwnerRole.name, remove=True)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.project))

    def test_sharing_through_v2_is_challenged(self):
        view = ProjectViewSetV2.as_view({"put": "share"})
        request = self.factory.put(
            "/", data={"username": "alice", "role": OwnerRole.name}, **self.extra
        )

        response = view(request, pk=self.project.pk)

        self.assert_challenged(response)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.project))

    def test_an_invalid_share_keeps_the_grant(self):
        """Validation comes first, so an unknown username does not spend it."""
        self.assert_challenged(self._share("alice", OwnerRole.name))
        grant = self._grant()

        response = self._share("nobody", OwnerRole.name, self._with_grant(grant))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))


@gating(
    GATE_INVITE_PROJECT_ADMIN,
    PROJECT_INVITATION_URL={"*": "https://example.com/register"},
)
@patch(
    "onadata.libs.serializers.project_invitation_serializer"
    ".send_project_invitation_email_async.delay"
)
class TestInviteProjectAdminGate(StepUpGateTestCase):
    """An invitation confers its role when accepted, so inviting someone as
    an owner or manager needs the same proof as sharing with them."""

    audience = GATE_INVITE_PROJECT_ADMIN

    def setUp(self):
        super().setUp()
        self._project_create()

    def _invite(self, method, payload, headers=None):
        view = ProjectViewSet.as_view({method: "invitations"})
        request = getattr(self.factory, method)(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.project.pk)

    def _create(self, role, headers=None, email="jane@example.com"):
        return self._invite("post", {"email": email, "role": role}, headers)

    def _pending(self, role):
        return self.project.invitations.create(
            email="jane@example.com",
            role=role,
            status=ProjectInvitation.Status.PENDING,
        )

    def _update(self, invitation, role, headers=None, email=None):
        payload = {
            "invitation_id": invitation.pk,
            "email": email or invitation.email,
            "role": role,
        }
        return self._invite("put", payload, headers)

    def test_inviting_a_manager_is_challenged(self, _send):
        response = self._create(ManagerRole.name)

        self.assert_challenged(response)
        self.assertFalse(self.project.invitations.exists())

    def test_a_grant_lets_the_invitation_through(self, _send):
        grant = self._grant()

        response = self._create(OwnerRole.name, self._with_grant(grant))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.invitations.get().role, OwnerRole.name)
        self.assert_spent(grant)

    def test_inviting_a_non_admin_is_not_challenged(self, _send):
        self.assert_challenged(self._create(OwnerRole.name))

        response = self._create(EditorRole.name)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.invitations.get().role, EditorRole.name)

    def test_raising_an_invitation_to_owner_is_challenged(self, _send):
        invitation = self._pending(EditorRole.name)

        response = self._update(invitation, OwnerRole.name)

        self.assert_challenged(response)
        invitation.refresh_from_db()
        self.assertEqual(invitation.role, EditorRole.name)

    def test_redirecting_an_admin_invitation_is_challenged(self, _send):
        invitation = self._pending(ManagerRole.name)

        response = self._update(
            invitation, ManagerRole.name, email="mallory@example.com"
        )

        self.assert_challenged(response)
        invitation.refresh_from_db()
        self.assertEqual(invitation.email, "jane@example.com")

    def test_keeping_an_invitations_admin_role_is_not_challenged(self, _send):
        invitation = self._pending(ManagerRole.name)
        self.assert_challenged(self._update(invitation, OwnerRole.name))

        response = self._update(invitation, ManagerRole.name)

        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.role, ManagerRole.name)

    def test_lowering_an_invitation_is_not_challenged(self, _send):
        invitation = self._pending(OwnerRole.name)
        self.assert_challenged(self._create(OwnerRole.name, email="kim@example.com"))

        response = self._update(invitation, EditorRole.name)

        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.role, EditorRole.name)

    def test_an_invalid_invitation_keeps_the_grant(self, _send):
        """Validation comes first, so a mistyped email does not spend it."""
        self.assert_challenged(self._create(OwnerRole.name))
        grant = self._grant()

        response = self._create(
            OwnerRole.name, self._with_grant(grant), email="not-an-email"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))
        self.assertFalse(self.project.invitations.exists())


@gating(GATE_SHARE_FORM_ADMIN)
class TestShareFormAdminGate(StepUpGateTestCase):
    """An owner or manager of a form can share it on and delete it, so a
    stolen session must not be able to appoint one."""

    audience = GATE_SHARE_FORM_ADMIN

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.alice = self._user("alice")
        self.tom = self._user("tom")

    def _share(self, username, role, headers=None):
        view = XFormViewSet.as_view({"post": "share"})
        request = self.factory.post(
            "/",
            data={"username": username, "role": role},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.xform.pk)

    def test_sharing_as_owner_is_challenged(self):
        response = self._share("alice", OwnerRole.name)

        self.assert_challenged(response)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

    def test_sharing_as_manager_is_challenged(self):
        response = self._share("alice", ManagerRole.name)

        self.assert_challenged(response)
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))

    def test_a_grant_lets_the_share_through(self):
        grant = self._grant()

        response = self._share("alice", OwnerRole.name, self._with_grant(grant))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
        self.assert_spent(grant)

    def test_one_new_admin_among_several_users_is_challenged(self):
        ShareXForm(self.xform, "alice", ManagerRole.name).save()
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.xform))

        response = self._share("alice,tom", ManagerRole.name)

        self.assert_challenged(response)
        self.assertFalse(ManagerRole.user_has_role(self.tom, self.xform))

    def test_a_non_admin_role_is_not_challenged(self):
        self.assert_challenged(self._share("tom", OwnerRole.name))

        response = self._share("alice", EditorRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.xform))

    def test_a_role_every_target_already_holds_is_not_challenged(self):
        ShareXForm(self.xform, "alice", OwnerRole.name).save()
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))
        self.assert_challenged(self._share("tom", OwnerRole.name))

        response = self._share("alice", OwnerRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.xform))

    def test_an_invalid_share_keeps_the_grant(self):
        """Validation comes first, so an unknown username does not spend it."""
        self.assert_challenged(self._share("alice", OwnerRole.name))
        grant = self._grant()

        response = self._share("nobody", OwnerRole.name, self._with_grant(grant))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))


@gating(GATE_PUBLISH_DATA)
class TestPublishProjectDataGate(StepUpGateTestCase):
    """A public project's forms and data are readable by anyone, so a stolen
    session must not be able to publish them."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assertFalse(self.project.shared)
        self.assertFalse(self.xform.shared_data)

    def _patch(self, data, headers=None, viewset=ProjectViewSet):
        view = viewset.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, **{**self.extra, **(headers or {})}
        )
        return view(request, pk=self.project.pk)

    def _make_public(self):
        Project.objects.filter(pk=self.project.pk).update(shared=True)
        XForm.objects.filter(pk=self.xform.pk).update(shared=True, shared_data=True)

    def _reload(self):
        self.project.refresh_from_db()
        self.xform.refresh_from_db()

    def test_making_a_project_public_is_challenged(self):
        response = self._patch({"public": True})

        self.assert_challenged(response)
        self._reload()
        self.assertFalse(self.project.shared)
        self.assertFalse(self.xform.shared_data)

    def test_a_full_update_making_a_project_public_is_challenged(self):
        view = ProjectViewSet.as_view({"put": "update"})
        data = {
            "name": "demo",
            "owner": f"http://testserver/api/v1/users/{self.user.username}",
            "public": True,
        }
        request = self.factory.put("/", data=data, **self.extra)

        response = view(request, pk=self.project.pk)

        self.assert_challenged(response)
        self._reload()
        self.assertFalse(self.project.shared)

    def test_making_a_project_public_through_v2_is_challenged(self):
        response = self._patch({"public": True}, viewset=ProjectViewSetV2)

        self.assert_challenged(response)
        self._reload()
        self.assertFalse(self.project.shared)

    def test_a_grant_lets_the_project_go_public(self):
        grant = self._grant()

        response = self._patch({"public": True}, self._with_grant(grant))

        self.assertEqual(response.status_code, 200)
        self._reload()
        self.assertTrue(self.project.shared)
        self.assertTrue(self.xform.shared_data)
        self.assert_spent(grant)

    def test_editing_a_public_project_with_a_private_form_is_challenged(self):
        """Every save of a public project makes its private forms public."""
        Project.objects.filter(pk=self.project.pk).update(shared=True)

        response = self._patch({"name": "renamed"})

        self.assert_challenged(response)
        self._reload()
        self.assertEqual(self.project.name, "demo")
        self.assertFalse(self.xform.shared_data)

    def test_editing_a_public_project_with_public_forms_is_not_challenged(self):
        Project.objects.filter(pk=self.project.pk).update(shared=True)
        self.assert_challenged(self._patch({"name": "renamed"}))
        XForm.objects.filter(pk=self.xform.pk).update(shared=True, shared_data=True)

        response = self._patch({"name": "renamed"})

        self.assertEqual(response.status_code, 200)
        self._reload()
        self.assertEqual(self.project.name, "renamed")

    def test_making_a_project_private_is_not_challenged(self):
        self.assert_challenged(self._patch({"public": True}))
        self._make_public()

        response = self._patch({"public": False})

        self.assertEqual(response.status_code, 200)
        self._reload()
        self.assertFalse(self.project.shared)
        self.assertFalse(self.xform.shared_data)

    def test_an_invalid_update_keeps_the_grant(self):
        """Validation comes first, so a blank name does not spend it."""
        self.assert_challenged(self._patch({"public": True}))
        grant = self._grant()

        response = self._patch({"public": True, "name": ""}, self._with_grant(grant))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))
        self._reload()
        self.assertFalse(self.project.shared)


@gating(GATE_PUBLISH_DATA)
class TestPublishFormDataGate(StepUpGateTestCase):
    """A public form's data is readable by anyone, so a stolen session must
    not be able to publish it."""

    audience = GATE_PUBLISH_DATA

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assertFalse(self.xform.shared)
        self.assertFalse(self.xform.shared_data)

    def _patch(self, data, headers=None):
        view = XFormViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, **{**self.extra, **(headers or {})}
        )
        return view(request, pk=self.xform.pk)

    def test_making_form_data_public_is_challenged(self):
        response = self._patch({"public_data": True})

        self.assert_challenged(response)
        self.xform.refresh_from_db()
        self.assertFalse(self.xform.shared_data)

    def test_making_a_form_public_is_challenged(self):
        response = self._patch({"public": True})

        self.assert_challenged(response)
        self.xform.refresh_from_db()
        self.assertFalse(self.xform.shared)

    def test_a_grant_lets_the_form_data_go_public(self):
        grant = self._grant()

        response = self._patch({"public_data": True}, self._with_grant(grant))

        self.assertEqual(response.status_code, 200)
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.shared_data)
        self.assert_spent(grant)

    def test_making_form_data_private_is_not_challenged(self):
        self.assert_challenged(self._patch({"public_data": True}))
        XForm.objects.filter(pk=self.xform.pk).update(shared=True, shared_data=True)

        response = self._patch({"public": False, "public_data": False})

        self.assertEqual(response.status_code, 200)
        self.xform.refresh_from_db()
        self.assertFalse(self.xform.shared)
        self.assertFalse(self.xform.shared_data)

    def test_an_invalid_update_keeps_the_grant(self):
        """Validation comes first, so a malformed public key does not spend it."""
        self.assert_challenged(self._patch({"public_data": True}))
        grant = self._grant()

        response = self._patch(
            {"public_data": True, "public_key": "not-a-key"},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))
        self.xform.refresh_from_db()
        self.assertFalse(self.xform.shared_data)
