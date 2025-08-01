# -*- coding: utf-8 -*-
"""
Test /orgs API endpoint implementation.
"""

import json
import sys
from builtins import str as text
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test.utils import override_settings
from django.utils import timezone

from guardian.shortcuts import get_perms
from rest_framework import status

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    Team,
    get_organization_members_team,
)
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import (
    add_user_to_organization,
    get_or_create_organization_owners_team,
)
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.logger.models.kms import KMSKey
from onadata.apps.logger.models.project import Project
from onadata.apps.main.models import UserProfile
from onadata.libs.exceptions import EncryptionError
from onadata.libs.permissions import ROLES, DataEntryRole, OwnerRole
from onadata.libs.utils.cache_tools import (
    PROJ_OWNER_CACHE,
    PROJ_PERM_CACHE,
    PROJ_TEAM_USERS_CACHE,
)


# pylint: disable=too-many-public-methods
class TestOrganizationProfileViewSet(TestAbstractViewSet):
    """
    Test /orgs API endpoint implementation.
    """

    def setUp(self):
        super().setUp()
        self.view = OrganizationProfileViewSet.as_view(
            {
                "get": "list",
                "post": "create",
                "patch": "partial_update",
            }
        )

    def tearDown(self):
        """
        Specific to clear cache between tests
        """
        super(TestOrganizationProfileViewSet, self).tearDown()
        cache.clear()

    def test_partial_updates(self):
        self._org_create()
        metadata = {"computer": "mac"}
        json_metadata = json.dumps(metadata)
        data = {"metadata": json_metadata}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user="denoinc")
        profile = OrganizationProfile.objects.get(name="Dennis")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.metadata, metadata)

    def test_partial_updates_invalid(self):
        self._org_create()
        data = {"name": "a" * 31}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["name"], ["Ensure this field has no more than 30 characters."]
        )

    def test_orgs_list(self):
        self._org_create()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data["metadata"]
        del self.company_data["email"]
        del self.company_data["encryption_keys"]
        self.assertEqual(response.data, [self.company_data])

        # inactive organization
        self.organization.user.is_active = False
        self.organization.user.save()

        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_for_anonymous_user(self):
        self._org_create()
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_for_authenticated_user(self):
        self._org_create()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data["metadata"]
        del self.company_data["email"]
        del self.company_data["encryption_keys"]
        self.assertEqual(response.data, [self.company_data])

    def test_orgs_list_shared_with_user(self):
        authenticated_user = self.user
        user_in_shared_organization, _ = User.objects.get_or_create(
            username="the_stalked"
        )

        UserProfile.objects.get_or_create(
            user=user_in_shared_organization, name=user_in_shared_organization.username
        )

        unshared_organization, _ = User.objects.get_or_create(username="NotShared")
        unshared_organization_profile, _ = OrganizationProfile.objects.get_or_create(
            user=unshared_organization, creator=authenticated_user
        )

        add_user_to_organization(unshared_organization_profile, authenticated_user)

        shared_organization, _ = User.objects.get_or_create(username="Shared")
        shared_organization_profile, _ = OrganizationProfile.objects.get_or_create(
            user=shared_organization, creator=user_in_shared_organization
        )

        add_user_to_organization(shared_organization_profile, authenticated_user)

        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertTrue(len(response.data), 2)
        request = self.factory.get(
            "/", data={"shared_with": "the_stalked"}, **self.extra
        )
        response = self.view(request)
        self.assertEqual(len(response.data), 1)

    def test_orgs_list_restricted(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "list"})

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, "alice")

        request = self.factory.get("/", **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, [])

    def test_orgs_get(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Expected URL keyword argument `user`."}
        )
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.company_data)
        self.assertIn("users", list(response.data))
        for user in response.data["users"]:
            self.assertEqual(user["role"], "owner")
            self.assertTrue(isinstance(user["user"], text))

    def test_orgs_get_not_creator(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "retrieve"})
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        previous_user = self.user
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, "alice")
        self.assertNotEqual(previous_user, self.user)
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data["email"]
        del self.company_data["metadata"]
        del self.company_data["encryption_keys"]
        self.assertEqual(response.data, self.company_data)
        self.assertIn("users", list(response.data))
        for user in response.data["users"]:
            self.assertEqual(user["role"], "owner")
            self.assertTrue(isinstance(user["user"], text))

    def test_orgs_get_anon(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/")
        response = view(request, user="denoinc")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        del self.company_data["email"]
        del self.company_data["metadata"]
        del self.company_data["encryption_keys"]
        self.assertEqual(response.data, self.company_data)
        self.assertIn("users", list(response.data))
        for user in response.data["users"]:
            self.assertEqual(user["role"], "owner")
            self.assertTrue(isinstance(user["user"], text))

    def test_orgs_create(self):
        self._org_create()
        self.assertTrue(self.organization.user.is_active)
        self.assertEqual(self.organization.email, "mail@mail-server.org")

    def test_orgs_create_without_name(self):
        data = {
            "org": "denoinc",
            "city": "Denoville",
            "country": "US",
            "email": "user@mail.org",
            "home_page": "deno.com",
            "twitter": "denoinc",
            "description": "",
            "address": "",
            "phonenumber": "",
            "require_auth": False,
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.data, {"name": ["This field is required."]})

    def test_org_create_and_fetch_by_admin_user(self):
        org_email = "mail@mail-sever.org"
        data = {
            "name": "denoinc",
            "org": "denoinc",
            "city": "Denoville",
            "country": "US",
            "home_page": "deno.com",
            "twitter": "denoinc",
            "email": org_email,
            "description": "",
            "address": "",
            "phonenumber": "",
            "require_auth": False,
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json"
        )
        request.user = self.user
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], org_email)

    def test_org_create_with_anonymous_user(self):
        data = {
            "name": "denoinc",
            "org": "denoinc",
            "city": "Denoville",
            "country": "US",
            "home_page": "deno.com",
            "twitter": "denoinc",
            "description": "",
            "address": "",
            "phonenumber": "",
            "require_auth": False,
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

    def test_orgs_members_list(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "members"})

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.data, ["denoinc"])

    def test_add_members_to_org_username_required(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post("/", data={}, **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"username": ["This field may not be null."]})

    def test_add_members_to_org_user_does_not_exist(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        data = {"username": "aboy"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"username": ["User 'aboy' does not exist."]})

    def test_add_members_to_org(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self.profile_data["username"] = "aboy"
        self.profile_data["email"] = "aboy@org.com"
        self._create_user_profile()
        data = {"username": "aboy"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))
        team = Team.objects.get(name=f"{self.organization.user.username}#members")
        self.assertTrue(team.user_set.filter(username="aboy").exists())

    def test_inactive_members_not_listed(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self.profile_data["username"] = "aboy"
        self.profile_data["email"] = "aboy@org.com"
        self._create_user_profile()
        data = {"username": "aboy"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

        # Ensure inactive/soft-deleted users are not present in the list
        user = User.objects.get(username="aboy")
        user.is_active = False
        deletion_suffix = timezone.now().strftime("-deleted-at-%s")
        user.username += deletion_suffix
        user.email += deletion_suffix
        user.save()

        view = OrganizationProfileViewSet.as_view({"get": "members"})

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Cache-Control"), None)

        # ensure the inactive aboy user is not in the list
        self.assertEqual(response.data, ["denoinc"])

    def test_add_members_to_org_user_org_account(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        username = "second_inc"

        # Create second org
        org_data = {"org": username}
        self._org_create(org_data=org_data)

        data = {"username": username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"username": ["Cannot add org account `second_inc` as member."]},
        )

    def test_member_sees_orgs_added_to(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"get": "list", "post": "members"})

        member = "aboy"
        cur_username = self.profile_data["username"]
        self.profile_data["username"] = member
        self._login_user_and_profile()
        self.profile_data["username"] = cur_username
        self._login_user_and_profile()

        data = {"username": member}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

        self.profile_data["username"] = member
        self._login_user_and_profile()

        expected_data = self.company_data
        expected_data["users"].append(
            {
                "first_name": "Bob",
                "last_name": "erama",
                "role": "member",
                "user": member,
                "gravatar": self.user.profile.gravatar,
            }
        )
        del expected_data["metadata"]
        del expected_data["email"]
        del self.company_data["encryption_keys"]

        request = self.factory.get("/", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        response_data = dict(response.data[0])
        returned_users = response_data.pop("users")
        expected_users = expected_data.pop("users")
        self.assertDictEqual(response_data, expected_data)
        for user in expected_users:
            self.assertIn(user, returned_users)

    def test_role_for_org_non_owner(self):
        # creating org with member
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {"get": "retrieve", "post": "members"}
        )

        self.profile_data["username"] = "aboy"
        self._create_user_profile()
        data = {"username": "aboy"}
        user_role = "member"
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")

        # getting profile
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "mail@mail-server.org")
        self.assertIn("users", list(response.data))

        for user in response.data["users"]:
            username = user["user"]
            role = user["role"]
            expected_role = (
                "owner"
                if username == "denoinc" or username == self.user.username
                else user_role
            )
            self.assertEqual(role, expected_role)

        # getting profile as a member
        request = self.factory.get("/", **self.extra)
        request.user = User.objects.get(username="aboy")
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)

        # get profile as a anonymous user
        request = self.factory.get("/", **self.extra)
        request.user = AnonymousUser()
        request.headers = None
        request.META["HTTP_AUTHORIZATION"] = ""
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertFalse("email" in response.data)

    def test_add_members_to_org_with_anonymous_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self._create_user_profile(extra_post_data={"username": "aboy"})
        data = {"username": "aboy"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json"
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(set(response.data), set(["denoinc", "aboy"]))

    def test_add_members_to_org_with_non_member_user(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self._create_user_profile(extra_post_data={"username": "aboy"})
        data = {"username": "aboy"}
        previous_user = self.user
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)
        self.assertEqual(self.user.username, "alice")
        self.assertNotEqual(previous_user, self.user)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(set(response.data), set(["denoinc", "aboy"]))

    def test_remove_members_from_org(self):
        self._org_create()
        newname = "aboy"
        view = OrganizationProfileViewSet.as_view(
            {"post": "members", "delete": "members"}
        )

        self._create_user_profile(extra_post_data={"username": newname})

        data = {"username": newname}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", newname]))

        request = self.factory.delete(
            "/", json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, ["denoinc"])

        newname = "aboy2"
        self._create_user_profile(extra_post_data={"username": newname})

        data = {"username": newname}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", newname]))

        request = self.factory.delete("/?username={}".format(newname), **self.extra)

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, ["denoinc"])

        # Removes users from org projects.
        # Create a project
        project_data = {"owner": self.company_data["user"]}
        self._project_create(project_data)

        # Create alice
        alice = "alice"
        self._create_user_profile(extra_post_data={"username": alice})
        alice_data = {"username": alice, "role": "owner"}
        request = self.factory.post(
            "/",
            data=json.dumps(alice_data),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        # alice is in project
        projectView = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get("users")
        users_in_users = [user["user"] for user in project_users]

        self.assertIn(alice, users_in_users)

        # remove alice from org
        request = self.factory.delete("/?username={}".format(alice), **self.extra)

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(response.data, ["alice"])

        # alice is also removed from project
        projectView = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get("users")
        users_in_users = [user["user"] for user in project_users]

        self.assertNotIn(alice, users_in_users)

    def test_orgs_create_with_mixed_case(self):
        data = {
            "name": "denoinc",
            "org": "DenoINC",
            "city": "Denoville",
            "country": "US",
            "home_page": "deno.com",
            "twitter": "denoinc",
            "description": "",
            "email": "user@mail.com",
            "address": "",
            "phonenumber": "",
            "require_auth": False,
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)

        data["org"] = "denoinc"
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Organization %s already exists." % data["org"], response.data["org"]
        )

    def test_publish_xls_form_to_organization_project(self):
        self._org_create()
        project_data = {"owner": self.company_data["user"]}
        self._project_create(project_data)
        self._publish_xls_form_to_project()
        self.assertTrue(OwnerRole.user_has_role(self.user, self.xform))

    def test_put_change_role(self):
        self._org_create()
        newname = "aboy"
        view = OrganizationProfileViewSet.as_view(
            {"get": "retrieve", "post": "members", "put": "members"}
        )

        self.profile_data["username"] = newname
        self._create_user_profile()
        data = {"username": newname}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sorted(response.data), sorted(["denoinc", newname]))

        user_role = "editor"
        data = {"username": newname, "role": user_role}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.data), sorted(["denoinc", newname]))

        # getting profile
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("users", list(response.data))

        for user in response.data["users"]:
            username = user["user"]
            role = user["role"]
            expected_role = (
                "owner"
                if username == "denoinc" or username == self.user.username
                else user_role
            )
            self.assertEqual(role, expected_role)

    def test_put_require_role(self):
        self._org_create()
        newname = "aboy"
        view = OrganizationProfileViewSet.as_view(
            {"get": "retrieve", "post": "members", "put": "members"}
        )

        self.profile_data["username"] = newname
        self._create_user_profile()
        data = {"username": newname}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", newname]))

        data = {"username": newname}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)

    def test_put_bad_role(self):
        self._org_create()
        newname = "aboy"
        view = OrganizationProfileViewSet.as_view(
            {"get": "retrieve", "post": "members", "put": "members"}
        )

        self.profile_data["username"] = newname
        self._create_user_profile()
        data = {"username": newname}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", newname]))

        data = {"username": newname, "role": 42}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)

    @override_settings(DEFAULT_FROM_EMAIL="noreply@ona.io")
    @patch("onadata.libs.serializers.organization_member_serializer.send_mail")
    def test_add_members_to_org_email(self, mock_email):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self.profile_data["username"] = "aboy"
        self.profile_data["email"] = "aboy@org.com"
        self._create_user_profile()
        data = {"username": "aboy", "email_msg": "You have been add to denoinc"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_email.called)
        mock_email.assert_called_with(
            "aboy, You have been added to Dennis organisation.",
            "You have been add to denoinc",
            "noreply@ona.io",
            ("aboy@org.com",),
        )
        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

    @override_settings(DEFAULT_FROM_EMAIL="noreply@ona.io")
    @patch("onadata.libs.serializers.organization_member_serializer.send_mail")
    def test_add_members_to_org_email_custom_subj(self, mock_email):
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self.profile_data["username"] = "aboy"
        self.profile_data["email"] = "aboy@org.com"
        self._create_user_profile()
        data = {
            "username": "aboy",
            "email_msg": "You have been add to denoinc",
            "email_subject": "Your are made",
        }
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_email.called)
        mock_email.assert_called_with(
            "Your are made",
            "You have been add to denoinc",
            "noreply@ona.io",
            ("aboy@org.com",),
        )
        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

    def test_add_members_to_org_with_role(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {"post": "members", "get": "retrieve"}
        )

        self.profile_data["username"] = "aboy"
        self._create_user_profile()
        data = {"username": "aboy", "role": "editor"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

        # getting profile
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        # items can be in any order
        self.assertTrue(
            any(
                item["user"] == "aboy" and item["role"] == "editor"
                for item in response.data["users"]
            )
        )

    def test_add_members_to_owner_role(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {"post": "members", "get": "retrieve", "put": "members"}
        )

        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user

        data = {"username": "aboy", "role": "owner"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        self.assertEqual(set(response.data), set(["denoinc", "aboy"]))

        # getting profile
        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        aboy_data = {"user": "aboy", "role": "owner"}
        self.assertTrue(
            any(  # Order doesn't matter. aboy can be first or last
                all(item.get(key) == value for key, value in aboy_data.items())
                for item in response.data["users"]
            )
        )

        owner_team = get_or_create_organization_owners_team(self.organization)

        self.assertIn(aboy, owner_team.user_set.all())

        # test user removed from owner team when role changed
        data = {"username": "aboy", "role": "editor"}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)

        owner_team = get_or_create_organization_owners_team(self.organization)

        self.assertNotIn(aboy, owner_team.user_set.all())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_org_members_added_to_projects(self):
        # create org
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {"post": "members", "get": "retrieve", "put": "members"}
        )
        # create a proj
        project_data = {"owner": self.company_data["user"]}
        self._project_create(project_data)

        with self.captureOnCommitCallbacks(execute=True):
            self._publish_xls_form_to_project()

        # create aboy
        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user

        data = {"username": "aboy", "role": "owner"}
        request = self.factory.post(
            "/",
            data=json.dumps(data),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        # create alice
        self.profile_data["username"] = "alice"
        alice = self._create_user_profile().user
        alice_data = {"username": "alice", "role": "owner"}
        request = self.factory.post(
            "/",
            data=json.dumps(alice_data),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        # Assert that user added in org is added to teams in proj
        aboy.refresh_from_db()
        alice.refresh_from_db()
        self.assertTrue(OwnerRole.user_has_role(aboy, self.project))
        self.assertTrue(OwnerRole.user_has_role(alice, self.project))
        self.assertTrue(OwnerRole.user_has_role(aboy, self.xform))
        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))

        # Org admins are added to owners in project
        projectView = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = projectView(request, pk=self.project.pk)
        project_users = response.data.get("users")
        users_in_users = [user["user"] for user in project_users]

        self.assertIn("bob", users_in_users)
        self.assertIn("denoinc", users_in_users)
        self.assertIn("aboy", users_in_users)
        self.assertIn("alice", users_in_users)

    def test_member_added_to_org_with_correct_perms(self):
        view = OrganizationProfileViewSet.as_view({"post": "members"})

        self._org_create()
        project_data = {"owner": self.company_data["user"]}
        self._project_create(project_data)

        members_team = get_organization_members_team(self.organization)
        project_1 = self.project

        # Ensure team has no permissions
        self.assertEqual(get_perms(members_team, self.project), [])

        # set DataEntryRole role of project on team
        DataEntryRole.add(members_team, self.project)

        # Ensure team has correct permissions
        self.assertEqual(
            sorted(DataEntryRole.class_to_permissions[Project]),
            sorted(get_perms(members_team, self.project)),
        )

        # Extra project with no role
        project_data = {"owner": self.company_data["user"], "name": "proj2"}
        self._project_create(project_data)
        project_2 = self.project

        # New members & managers gain default team permissions on projects
        self.profile_data["username"] = "aboy"
        self.profile_data["email"] = "aboy@org.com"
        userprofile = self._create_user_profile()

        data = {"username": "aboy", "role": "manager"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertCountEqual(response.data, ["denoinc", "aboy"])

        project_view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get(
            "/", **{"HTTP_AUTHORIZATION": f"Token {userprofile.user.auth_token}"}
        )

        project_team_cache_key = f"{PROJ_TEAM_USERS_CACHE}{project_1.pk}"
        project_perm_cache_key = f"{PROJ_PERM_CACHE}{project_1.pk}"
        cache.delete(project_team_cache_key)
        cache.delete(project_perm_cache_key)
        self.assertTrue(cache.get(project_team_cache_key) is None)
        self.assertTrue(cache.get(project_perm_cache_key) is None)

        response = project_view(request, pk=project_1.pk)
        self.assertEqual(response.status_code, 200)
        expected_users = [
            {
                "is_org": False,
                "metadata": {},
                "first_name": "Bob",
                "last_name": "erama",
                "user": "aboy",
                "role": DataEntryRole.name,
            },
            {
                "is_org": True,
                "metadata": {},
                "first_name": "Dennis",
                "last_name": "",
                "user": "denoinc",
                "role": "owner",
            },
            {
                "is_org": False,
                "metadata": {},
                "first_name": "Bob",
                "last_name": "erama",
                "user": "bob",
                "role": "owner",
            },
        ]
        expected_teams = [
            {"name": "denoinc#Owners", "role": "owner", "users": ["bob"]},
            {
                "name": "denoinc#members",
                "role": DataEntryRole.name,
                "users": ["denoinc", "aboy"],
            },
        ]
        returned_data = response.data

        # Ensure default team role has been set on the project
        self.assertEqual(returned_data["teams"], expected_teams)

        # Ensure new managers are not granted the manager role
        # on projects they did not create
        self.assertEqual(len(returned_data["users"]), len(expected_users))
        for user in expected_users:
            self.assertTrue(user in returned_data["users"])

        # Ensure members team has no permission on the project
        self.assertEqual(get_perms(members_team, project_2), [])

        # Ensure no permissions are granted if team has no permissions
        project_team_cache_key = f"{PROJ_TEAM_USERS_CACHE}{project_2.pk}"
        project_perm_cache_key = f"{PROJ_PERM_CACHE}{project_2.pk}"
        project_cache_key = f"{PROJ_OWNER_CACHE}{project_2.pk}"
        cache.delete(project_cache_key)
        cache.delete(project_team_cache_key)
        cache.delete(project_perm_cache_key)
        self.assertTrue(cache.get(project_team_cache_key) is None)
        self.assertTrue(cache.get(project_perm_cache_key) is None)

        request = self.factory.get(
            "/", **{"HTTP_AUTHORIZATION": f"Token {userprofile.user.auth_token}"}
        )
        response = project_view(request, pk=project_2.pk)
        # User shouldn't have any permissions to view the project
        self.assertEqual(response.status_code, 404)

    def test_put_role_user_none_existent(self):
        self._org_create()
        newname = "i-do-no-exist"
        view = OrganizationProfileViewSet.as_view(
            {"get": "retrieve", "post": "members", "put": "members"}
        )

        data = {"username": newname, "role": "editor"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)

    def test_update_org_name(self):
        self._org_create()

        # update name and email
        data = {"name": "Dennis2", "email": "dennis@mail.com"}
        request = self.factory.patch("/", data=data, **self.extra)
        response = self.view(request, user="denoinc")
        self.assertEqual(response.data["name"], "Dennis2")
        self.assertEqual(response.status_code, 200)

        # check in user profile endpoint
        view_user = UserProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)

        response = view_user(request, user="denoinc")
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Dennis2")

    def test_org_always_has_admin_or_owner(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {
                "put": "members",
            }
        )
        data = {"username": self.user.username, "role": "editor"}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"non_field_errors": ["Organization cannot be without an owner"]},
        )

    def test_owner_not_allowed_to_be_removed(self):
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {
                "post": "members",
                "delete": "members",
                "get": "retrieve",
            }
        )

        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user

        data = {"username": aboy.username, "role": "owner"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), set(["denoinc", aboy.username]))

        self.profile_data["username"] = "aboy2"
        aboy2 = self._create_user_profile().user

        data = {"username": aboy2.username, "role": "owner"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(response.data), set(["denoinc", aboy.username, aboy2.username])
        )

        data = {"username": aboy2.username}
        request = self.factory.delete(
            "/", json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)
        for user in ["denoinc", aboy.username]:
            self.assertIn(user, response.data)

        # at this point we have bob and aboy as owners
        data = {"username": aboy.username}
        request = self.factory.delete(
            "/", json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 200)

        # at this point we only have bob as the owner
        data = {"username": self.user.username}
        request = self.factory.delete(
            "/", json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user="denoinc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"non_field_errors": ["Organization cannot be without an owner"]},
        )

    def test_orgs_delete(self):
        self._org_create()
        self.assertTrue(self.organization.user.is_active)

        view = OrganizationProfileViewSet.as_view({"delete": "destroy"})

        request = self.factory.delete("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(204, response.status_code)

        self.assertEqual(
            0, OrganizationProfile.objects.filter(user__username="denoinc").count()
        )
        self.assertEqual(0, User.objects.filter(username="denoinc").count())

    def test_orgs_non_creator_delete(self):
        self._org_create()

        view = OrganizationProfileViewSet.as_view(
            {"delete": "members", "post": "members"}
        )

        self.profile_data["username"] = "alice"
        self.profile_data["email"] = "alice@localhost.com"
        self._create_user_profile()

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        request = self.factory.post(
            "/",
            data=json.dumps(alice_data),
            content_type="application/json",
            **self.extra,
        )

        response = view(request, user="denoinc")
        expected_results = ["denoinc", "alice"]
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertCountEqual(expected_results, response.data)

        self._login_user_and_profile(extra_post_data=alice_data)

        request = self.factory.delete(
            "/",
            data=json.dumps(alice_data),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")
        expected_results = ["denoinc"]
        self.assertEqual(expected_results, response.data)

    def test_creator_in_users(self):
        """
        Test that the creator of the organization is returned
        in the value of the 'users' key within the response from /orgs
        """
        self._org_create()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        expected_user = {
            "user": self.user.username,
            "role": "owner",
            "first_name": "Bob",
            "last_name": "erama",
            "gravatar": self.user.profile.gravatar,
        }
        self.assertIn(expected_user, response.data[0]["users"])

    def test_creator_permissions(self):
        """
        Test that the creator of the organization has the necessary
        permissions
        """
        self._org_create()
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        orgs = OrganizationProfile.objects.filter(creator=self.user)
        self.assertEqual(orgs.count(), 1)
        org = orgs.first()

        self.assertTrue(OwnerRole.user_has_role(self.user, org))
        self.assertTrue(OwnerRole.user_has_role(self.user, org.userprofile_ptr))

        members_view = OrganizationProfileViewSet.as_view(
            {"post": "members", "delete": "members"}
        )

        # New admins should also have the required permissions
        self.profile_data["username"] = "dave"
        dave = self._create_user_profile().user

        data = {"username": "dave", "role": "owner"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = members_view(request, user="denoinc")
        self.assertEqual(response.status_code, 201)

        # Ensure user has role
        self.assertTrue(OwnerRole.user_has_role(dave, org))
        self.assertTrue(OwnerRole.user_has_role(dave, org.userprofile_ptr))

        # Permissions should be removed when the user is removed from
        # organization
        request = self.factory.delete(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = members_view(request, user="denoinc")
        expected_results = ["denoinc"]
        self.assertEqual(expected_results, response.data)

        # Ensure permissions are removed
        self.assertFalse(OwnerRole.user_has_role(dave, org))
        self.assertFalse(OwnerRole.user_has_role(dave, org.userprofile_ptr))

    @override_settings(TIME_ZONE="UTC")
    def test_encryption_keys(self):
        """Encryption keys are returned."""
        self.organization = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        mars_org = self._create_organization(
            username="mars", name="Mars Inc", created_by=self.user
        )
        content_type = ContentType.objects.get_for_model(OrganizationProfile)
        self.view = OrganizationProfileViewSet.as_view({"get": "retrieve"})

        # Make user owner
        OwnerRole.add(self.user, self.organization)
        # Active key should be returned
        active_key = KMSKey.objects.create(
            key_id="active-key",
            description="Active Key",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
            expiry_date=timezone.now() + timedelta(days=365),
            grace_end_date=timezone.now() + timedelta(days=395),
        )
        # Disabled key should not be returned
        KMSKey.objects.create(
            key_id="disabled-key",
            description="Disabled Key",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
            disabled_at=timezone.now(),
        )
        # Key from another organization should not be returned
        KMSKey.objects.create(
            key_id="mars-active-key",
            description="Mars Active Key",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=mars_org.pk,
            provider=KMSKey.KMSProvider.AWS,
            expiry_date=timezone.now() + timedelta(days=365),
        )

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="valigetta")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["encryption_keys"]), 1)
        self.assertEqual(
            response.data["encryption_keys"][0]["description"],
            active_key.description,
        )
        self.assertEqual(
            response.data["encryption_keys"][0]["date_created"],
            active_key.date_created.isoformat().replace("+00:00", "Z"),
        )
        self.assertEqual(
            response.data["encryption_keys"][0]["expiry_date"],
            active_key.expiry_date.isoformat().replace("+00:00", "Z"),
        )
        self.assertEqual(
            response.data["encryption_keys"][0]["grace_end_date"],
            active_key.grace_end_date.isoformat().replace("+00:00", "Z"),
        )
        self.assertFalse(response.data["encryption_keys"][0]["is_expired"])
        self.assertTrue(response.data["encryption_keys"][0]["is_automatic"])
        self.assertTrue(response.data["encryption_keys"][0]["is_active"])

        # is_automatic is False is key created manually
        active_key.created_by = self.user
        active_key.save()
        cache.clear()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="valigetta")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["encryption_keys"][0]["is_automatic"])

        # Only admins can view encryption keys
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)

        for role in ROLES:
            role_cls = ROLES.get(role)
            role_cls.add(self.user, self.organization)
            request = self.factory.get("/", **self.extra)
            response = self.view(request, user=self.organization.user.username)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)
                self.assertIn("encryption_keys", response.data)

            else:
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("encryption_keys", response.data)

    def test_no_encryption_keys(self):
        """No encryption keys found."""
        self.organization = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        self.view = OrganizationProfileViewSet.as_view({"get": "retrieve"})
        # Make user owner
        OwnerRole.add(self.user, self.organization)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["encryption_keys"]), 0)


@patch("onadata.libs.serializers.organization_serializer.rotate_key")
class RotateKeyTestCase(TestAbstractViewSet):
    """Tests for rotating encryption key"""

    def setUp(self):
        super().setUp()

        self.view = OrganizationProfileViewSet.as_view({"post": "rotate_key"})
        self._org_create()
        self.content_type = ContentType.objects.get_for_model(OrganizationProfile)
        self.kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-25",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        self.data = {"id": self.kms_key.id, "rotation_reason": "Test rotation"}

    @override_settings(TIME_ZONE="UTC")
    def test_rotate_key(self, mock_rotate_key):
        """Manually rotating a key works."""
        mock_rotate_key.return_value = new_key = KMSKey.objects.create(
            key_id="new-key",
            description="Key-2025-04-25",
            public_key="fake-pub-key",
            content_type=self.content_type,
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], new_key.id)
        self.assertEqual(response.data["description"], "Key-2025-04-25")
        self.assertEqual(
            response.data["date_created"],
            new_key.date_created.isoformat().replace("+00:00", "Z"),
        )
        self.assertFalse(response.data["is_expired"])
        self.assertIsNone(response.data["expiry_date"])
        self.assertIsNone(response.data["grace_end_date"])

        mock_rotate_key.assert_called_once_with(
            self.kms_key,
            rotated_by=self.user,
            rotation_reason=self.data["rotation_reason"],
        )

    def test_authentication_required(self, mock_rotate_key):
        """Authenticattion is required."""
        request = self.factory.post("/", data=self.data)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 401)

    def test_only_admins_allowed(self, mock_rotate_key):
        """Only org admins can rotate key."""
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)

        for role in ROLES:
            role_cls = ROLES.get(role)
            role_cls.add(self.user, self.organization)
            request = self.factory.post("/", data=self.data, **self.extra)
            response = self.view(request, user="denoinc")

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertNotEqual(response.status_code, 200)

    def test_invalid_key(self, mock_rotate_key):
        """Invalid key id is handled."""
        request = self.factory.post("/", data={"id": sys.maxsize}, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Key does not exist", str(response.data["id"]))

    def test_disabled_key(self, mock_rotate_key):
        """Rotatation for disabled key is not allowed."""
        self.kms_key.disabled_at = timezone.now()
        self.kms_key.save()

        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Key is inactive", str(response.data["id"]))

    def test_already_rotated_key(self, mock_rotate_key):
        """Rotation for already rotated key is not allowed."""
        self.kms_key.rotated_at = timezone.now()
        self.kms_key.save()

        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Key already rotated", str(response.data["id"]))

    def test_rotation_errors_captured(self, mock_rotate_key):
        """Rotation errors are captured."""
        mock_rotate_key.side_effect = EncryptionError("Key is disabled.")

        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Key is disabled", str(response.data["id"]))

    @patch("onadata.apps.api.viewsets.organization_profile_viewset.send_message")
    def test_audit_log_capture(self, mock_send_message, mock_rotate_key):
        """Audit log is captured."""
        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        mock_send_message.assert_called_once_with(
            instance_id=self.kms_key.id,
            target_id=self.kms_key.id,
            target_type="kmskey",
            user=self.user,
            message_verb="kmskey_rotated",
        )

    def test_rotation_reason_optional(self, mock_rotate_key):
        """Rotation reason is optional."""
        request = self.factory.post("/", data={"id": self.kms_key.id}, **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        mock_rotate_key.assert_called_once_with(
            self.kms_key,
            rotated_by=self.user,
            rotation_reason=None,
        )
