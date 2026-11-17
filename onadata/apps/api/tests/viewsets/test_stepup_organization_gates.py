# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on an organisation's require_auth, its owner and
manager roles, and its encryption key.
"""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType

from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    get_organization_members_team,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_OWNER,
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.tools import get_organization_members
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.v2.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV2,
)
from onadata.apps.logger.models.kms import KMSKey
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import (
    EditorRole,
    ManagerRole,
    OwnerRole,
    get_team_project_default_permissions,
)


@gating("require-auth-toggle")
class TestOrganisationRequireAuthGate(StepUpGateTestCase):
    """An organisation's profile is a UserProfile, so its require_auth is the
    same column the personal profile gates."""

    def setUp(self):
        super().setUp()
        self._org_create()

    def _patch_org(self, data, headers=None):
        view = OrganizationProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, format="json", **{**self.extra, **(headers or {})}
        )
        return view(request, user="denoinc")

    def _require_auth(self):
        return OrganizationProfile.objects.get(user__username="denoinc").require_auth

    def test_toggling_require_auth_is_challenged(self):
        self.assertFalse(self._require_auth())

        response = self._patch_org({"require_auth": True})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "require-auth-toggle")
        self.assertFalse(self._require_auth())

    def test_a_grant_lets_the_toggle_through(self):
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        response = self._patch_org(
            {"require_auth": True}, {"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._require_auth())

    def test_other_changes_are_not_challenged(self):
        self.assertEqual(self._patch_org({"require_auth": True}).status_code, 401)

        response = self._patch_org({"name": "Dennis Inc", "require_auth": False})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            OrganizationProfile.objects.get(user__username="denoinc").name,
            "Dennis Inc",
        )

    def test_an_invalid_sibling_field_keeps_the_grant(self):
        """The whole request is validated before the gate, so a field the
        write would reject answers 400 and leaves the grant for the retry."""
        grant = issue_grant(self.user.pk, "require-auth-toggle")

        response = self._patch_org(
            {"require_auth": True, "name": "x" * 31}, {"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)
        self.assertFalse(self._require_auth())
        self.assertTrue(spend_grant(self.user.pk, "require-auth-toggle", grant))

    def test_a_form_put_omitting_require_auth_is_gated(self):
        """A form-encoded PUT that leaves out a boolean writes it as false, so
        omitting the checkbox switches the setting off.

        The request renames the organisation. validate_org refuses the current
        name, and the request must otherwise be valid to reach the gate.
        """
        organization = OrganizationProfile.objects.get(user__username="denoinc")
        organization.require_auth = True
        organization.save()
        view = OrganizationProfileViewSet.as_view({"put": "update"})

        request = self.factory.put(
            "/",
            data={
                "org": "denoinc-renamed",
                "name": "Dennis",
                "email": "mail@mail-server.org",
            },
            format="multipart",
            **self.extra,
        )
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "require-auth-toggle")
        self.assertTrue(self._require_auth())


@gating("grant-org-admin")
class TestOrganisationAdminRoleGate(StepUpGateTestCase):
    """An owner or manager can change every gated setting of the
    organisation with their own factor, so a stolen session must not be able
    to appoint one."""

    def setUp(self):
        super().setUp()
        self._org_create()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.assertNotEqual(self.alice, self.user)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _member_request(
        self,
        method,
        role,
        headers=None,
        username="alice",
        viewset=OrganizationProfileViewSet,
    ):
        view = viewset.as_view({method: "members"})
        request = getattr(self.factory, method)(
            "/",
            data={"username": username, "role": role},
            format="json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, user="denoinc")

    def _add_member(self, role, headers=None):
        return self._member_request("post", role, headers)

    def _make_alice(self, role=None):
        self._add_user_to_organization(self.organization, self.alice, role)
        self.assertIn(self.alice, get_organization_members(self.organization))

    def test_appointing_an_owner_is_challenged(self):
        response = self._add_member("owner")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_a_grant_lets_the_owner_through(self):
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._add_member("owner", {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_other_roles_are_not_challenged(self):
        self.assertEqual(self._add_member("owner").status_code, 401)

        response = self._add_member("editor")

        self.assertEqual(response.status_code, 201)
        self.assertIn(self.alice, get_organization_members(self.organization))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_appointing_a_manager_through_v2_is_challenged(self):
        response = self._member_request(
            "post", "manager", viewset=OrganizationProfileViewSetV2
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    def test_re_appointing_an_owner_is_not_challenged(self):
        self.assertEqual(self._add_member("owner").status_code, 401)
        self._make_alice("owner")
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

        response = self._add_member("owner")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_demoting_an_owner_to_manager_is_not_challenged(self):
        self.assertEqual(self._add_member("owner").status_code, 401)
        self._make_alice("owner")
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

        response = self._member_request("put", "manager")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.organization))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_an_unknown_username_keeps_the_grant(self):
        """The username is validated first, so a typo does not spend it."""
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._member_request(
            "post", "owner", {"HTTP_X_STEP_UP_GRANT": grant}, username="nobody"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "grant-org-admin", grant))

    def test_promoting_a_member_to_owner_through_v1_put_is_challenged(self):
        self._make_alice()

        response = self._member_request("put", "owner")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_appointing_a_manager_through_v1_is_challenged(self):
        response = self._add_member("manager")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))

    def test_a_grant_lets_the_owner_through_v2(self):
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._member_request(
            "post",
            "owner",
            {"HTTP_X_STEP_UP_GRANT": grant},
            viewset=OrganizationProfileViewSetV2,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))

    def test_promoting_a_member_to_manager_through_v2_patch_is_challenged(self):
        self._make_alice()

        response = self._member_request(
            "patch", "manager", viewset=OrganizationProfileViewSetV2
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.organization))


@gating("share-team-admin")
class TestOrganisationMembersTeamGate(StepUpGateTestCase):
    """Adding a member shares every organisation project with them at the
    members team's role, and each form's meta permissions can turn that role
    into owner."""

    def setUp(self):
        super().setUp()
        self._org_create()
        org_url = f"http://testserver/api/v1/users/{self.organization.user.username}"
        self._project_create({"owner": org_url})
        members_team = get_organization_members_team(self.organization)
        ShareTeamProject(members_team, self.project, EditorRole.name).save()
        self._publish_xls_form_to_project()
        self.assertEqual(self.xform.user, self.organization.user)
        self.alice = self._create_user("alice", "alice", create_profile=True)

    def _add_member(self, headers=None):
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data={"username": "alice", "role": "editor"},
            format="json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, user=self.organization.user.username)

    def _alice_owns_the_form(self):
        return OwnerRole.user_has_role(self.alice, self.xform)

    def test_adding_a_member_meta_perms_make_an_owner_is_challenged(self):
        """The 401 names the audience and leaves the user out."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)

        response = self._add_member()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertNotIn(self.alice, get_organization_members(self.organization))
        self.assertFalse(self._alice_owns_the_form())

    def test_a_grant_lets_the_member_join(self):
        """With a grant the member joins and the meta permissions make them
        the form's owner."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._add_member({"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 201)
        self.assertIn(self.alice, get_organization_members(self.organization))
        self.assertTrue(self._alice_owns_the_form())
        self.assertFalse(spend_grant(self.user.pk, "share-team-admin", grant))

    def test_adding_an_existing_member_again_is_challenged(self):
        """Adding a member again shares every project with them again."""
        self.assertEqual(self._add_member().status_code, 201)
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self.assertFalse(self._alice_owns_the_form())

        response = self._add_member()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(self._alice_owns_the_form())

    def test_adding_a_member_who_holds_every_shared_role_is_not_challenged(self):
        """Once the meta permissions have made a member the form's owner,
        adding them again hands out nothing new."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self.assertEqual(self._add_member().status_code, 401)
        grant = issue_grant(self.user.pk, "share-team-admin")
        self._add_member({"HTTP_X_STEP_UP_GRANT": grant})
        self.assertTrue(self._alice_owns_the_form())

        response = self._add_member()

        self.assertEqual(response.status_code, 201)

    def test_joining_a_members_team_with_a_promoting_form_role_is_challenged(self):
        """A role the members team holds on a form, outside any project
        share, counts too once the form's meta permissions apply."""
        members_team = get_organization_members_team(self.organization)
        ShareTeamProject(
            members_team, self.project, EditorRole.name, remove=True
        ).save()
        self.assertEqual(
            get_team_project_default_permissions(members_team, self.project), ""
        )
        EditorRole.add(members_team, self.xform)
        self._set_meta_perms(EDITOR_BECOMES_OWNER)

        response = self._add_member()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertNotIn(self.alice, get_organization_members(self.organization))

    def test_the_default_meta_perms_are_not_challenged(self):
        """The default meta permissions leave the team's editors editors."""
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        self.assertEqual(self._add_member().status_code, 401)
        self._set_meta_perms("editor|dataentry|readonly")

        response = self._add_member()

        self.assertEqual(response.status_code, 201)
        self.assertIn(self.alice, get_organization_members(self.organization))
        self.assertFalse(self._alice_owns_the_form())


@gating("rotate-org-key")
@patch("onadata.libs.serializers.organization_serializer.rotate_key")
class TestOrganisationKeyRotationGate(StepUpGateTestCase):
    """Rotating the organisation's encryption key makes every device fetch
    the re-keyed forms, so a stolen session alone must not trigger it."""

    def setUp(self):
        super().setUp()
        self._org_create()
        self.content_type = ContentType.objects.get_for_model(OrganizationProfile)
        self.kms_key = self._key("fake-key-id")

    def _key(self, key_id):
        return KMSKey.objects.create(
            key_id=key_id,
            description="Key-2025-04-25",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
        )

    def _rotate(self, key_id, headers=None):
        view = OrganizationProfileViewSet.as_view({"post": "rotate_key"})
        request = self.factory.post(
            "/", data={"id": key_id}, **{**self.extra, **(headers or {})}
        )
        return view(request, user="denoinc")

    def test_rotating_the_key_is_challenged(self, mock_rotate_key):
        response = self._rotate(self.kms_key.id)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "rotate-org-key")
        mock_rotate_key.assert_not_called()

    def test_a_grant_lets_the_rotation_through(self, mock_rotate_key):
        mock_rotate_key.return_value = self._key("new-key")
        grant = issue_grant(self.user.pk, "rotate-org-key")

        response = self._rotate(self.kms_key.id, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 200)
        mock_rotate_key.assert_called_once()

    def test_an_invalid_key_keeps_the_grant(self, mock_rotate_key):
        """Validation comes first, so a mistyped key id does not spend it."""
        grant = issue_grant(self.user.pk, "rotate-org-key")

        response = self._rotate(0, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "rotate-org-key", grant))
        mock_rotate_key.assert_not_called()
