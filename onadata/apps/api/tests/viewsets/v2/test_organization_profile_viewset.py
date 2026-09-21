"""Tests for onadata.apps.api.viewsets.v2.organization_profile_viewset"""

import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_organization
from onadata.apps.api.viewsets.v2.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.main.models import UserProfile
from onadata.libs.utils.cache_tools import ORG_PROFILE_V2_CACHE


class GetOrganizationListTestCase(TestAbstractViewSet):
    """Tests for GET list of organizations"""

    def setUp(self):
        super().setUp()

        self.view = OrganizationProfileViewSet.as_view({"get": "list"})

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_get_all(self):
        """GET all organizations"""
        self._org_create()

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.assertEqual(
            response.data,
            [
                {
                    "url": "http://testserver/api/v2/orgs/denoinc",
                    "org": "denoinc",
                    "name": "Dennis",
                    "creator": "http://testserver/api/v1/users/bob",
                    "num_of_submissions": 0,
                    "date_modified": timezone.localtime(
                        self.organization.date_modified
                    ).isoformat(),
                }
            ],
        )

    def test_query_count(self):
        """The number of queries does not grow with the organizations listed"""
        self._org_create({"org": "alpha", "name": "Alpha"})
        self._org_create({"org": "bravo", "name": "Bravo"})
        # Warm up what is cached once, such as content types
        self.view(self.factory.get("/", **self.extra))

        with CaptureQueriesContext(connection) as queries_for_two:
            response = self.view(self.factory.get("/", **self.extra))

        self.assertEqual(len(response.data), 2)

        self._org_create({"org": "charlie", "name": "Charlie"})
        self._org_create({"org": "delta", "name": "Delta"})
        self._org_create({"org": "echo", "name": "Echo"})

        with CaptureQueriesContext(connection) as queries_for_five:
            response = self.view(self.factory.get("/", **self.extra))

        self.assertEqual(len(response.data), 5)
        self.assertEqual(len(queries_for_five), len(queries_for_two))

    def test_inactive_organization(self):
        """An inactive organization is left out"""
        self._org_create()
        self.organization.user.is_active = False
        self.organization.user.save()

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_anonymous_user(self):
        """An anonymous user is not shown any organization"""
        self._org_create()

        request = self.factory.get("/")
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_pagination(self):
        """`page` and `page_size` limit the organizations returned"""
        self._org_create({"org": "alpha", "name": "Alpha"})
        self._org_create({"org": "bravo", "name": "Bravo"})
        self._org_create({"org": "charlie", "name": "Charlie"})

        request = self.factory.get("/", data={"page": 1, "page_size": 2}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["alpha", "bravo"])

        request = self.factory.get("/", data={"page": 2, "page_size": 2}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["charlie"])

    def test_orgs_list_pagination_link_header(self):
        """The `Link` header points to the other pages"""
        self._org_create({"org": "alpha", "name": "Alpha"})
        self._org_create({"org": "bravo", "name": "Bravo"})
        self._org_create({"org": "charlie", "name": "Charlie"})
        self._org_create({"org": "delta", "name": "Delta"})

        request = self.factory.get("/", data={"page": 3, "page_size": 1}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Link"],
            (
                '<http://testserver/?page=2&page_size=1>; rel="prev", '
                '<http://testserver/?page=4&page_size=1>; rel="next", '
                '<http://testserver/?page=4&page_size=1>; rel="last", '
                '<http://testserver/?page=1&page_size=1>; rel="first"'
            ),
        )

    def test_orgs_list_ordered_by_username(self):
        """Paging through the list returns each organization once, by username"""
        self._org_create({"org": "charlie", "name": "Alpha Co"})
        self._org_create({"org": "alpha", "name": "Charlie Co"})
        self._org_create({"org": "bravo", "name": "Bravo Co"})

        orgs = []

        for page in (1, 2, 3):
            request = self.factory.get(
                "/", data={"page": page, "page_size": 1}, **self.extra
            )
            response = self.view(request)
            self.assertEqual(response.status_code, 200)
            orgs += [org["org"] for org in response.data]

        self.assertEqual(orgs, ["alpha", "bravo", "charlie"])

    def test_orgs_list_search_by_name(self):
        """`search` matches part of the organization's name, ignoring case"""
        self._org_create({"org": "alpha", "name": "Health Initiative"})
        self._org_create({"org": "bravo", "name": "Water Works"})

        request = self.factory.get("/", data={"search": "health"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["alpha"])

    def test_orgs_list_search_by_username(self):
        """`search` matches part of the organization's username, ignoring case"""
        self._org_create({"org": "healthorg", "name": "Alpha"})
        self._org_create({"org": "waterorg", "name": "Bravo"})

        request = self.factory.get("/", data={"search": "HEALTH"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["healthorg"])

    def test_orgs_list_search_with_shared_with(self):
        """`search` narrows down the organizations shared with a user"""
        member, _ = User.objects.get_or_create(username="the_stalked")
        UserProfile.objects.get_or_create(user=member, name=member.username)
        self._org_create({"org": "healthshared", "name": "Alpha"})
        add_user_to_organization(self.organization, member)
        self._org_create({"org": "watershared", "name": "Bravo"})
        add_user_to_organization(self.organization, member)
        self._org_create({"org": "healthsolo", "name": "Charlie"})

        request = self.factory.get(
            "/",
            data={"shared_with": "the_stalked", "search": "health"},
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["healthshared"])

    def test_orgs_list_search_restricted(self):
        """`search` only returns organizations the user has access to"""
        self._org_create({"org": "healthbob", "name": "Alpha"})
        self._org_create({"org": "healthalice", "name": "Bravo"})
        health_alice = self.organization
        self._org_create({"org": "wateralice", "name": "Charlie"})
        water_alice = self.organization
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)
        add_user_to_organization(health_alice, self.user)
        add_user_to_organization(water_alice, self.user)

        request = self.factory.get("/", data={"search": "health"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["healthalice"])

    def test_orgs_list_search_with_pagination(self):
        """Search results are paginated"""
        self._org_create({"org": "aqua", "name": "Aqua"})
        self._org_create({"org": "healtha", "name": "Alpha"})
        self._org_create({"org": "healthb", "name": "Bravo"})
        self._org_create({"org": "healthc", "name": "Charlie"})

        request = self.factory.get(
            "/", data={"search": "health", "page": 1, "page_size": 2}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["healtha", "healthb"])
        self.assertEqual(
            response["Link"],
            (
                '<http://testserver/?page=2&page_size=2&search=health>; rel="next", '
                '<http://testserver/?page=2&page_size=2&search=health>; rel="last"'
            ),
        )

        request = self.factory.get(
            "/", data={"search": "health", "page": 2, "page_size": 2}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["healthc"])

    def _create_orgs_with_roles(self):
        """Log in alice, who holds a different role in each organization"""
        # bob creates the organizations
        orgs = {}
        names = {
            "ownedorg": "Health Owned",
            "managedorg": "Water Managed",
            "editororg": "Health Editor",
            "memberorg": "Water Member",
            "noorg": "Health None",
        }

        for username, name in names.items():
            self._org_create({"org": username, "name": name})
            orgs[username] = self.organization

        # carol only belongs to two of the organizations
        carol = self._create_user_profile(
            {"username": "carol", "email": "carol@localhost.com"}
        ).user
        add_user_to_organization(orgs["ownedorg"], carol)
        add_user_to_organization(orgs["editororg"], carol)
        # alice holds a different role in each, and none in `noorg`
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)
        add_user_to_organization(orgs["ownedorg"], self.user, "owner")
        add_user_to_organization(orgs["managedorg"], self.user, "manager")
        add_user_to_organization(orgs["editororg"], self.user, "editor")
        add_user_to_organization(orgs["memberorg"], self.user)

    def test_orgs_list_role_owner(self):
        """`role=owner` returns only the organizations the user owns"""
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "owner"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["ownedorg"])

    def test_orgs_list_role_manager(self):
        """`role=manager` returns the organizations the user manages or owns"""
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "manager"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [org["org"] for org in response.data], ["managedorg", "ownedorg"]
        )

    def test_orgs_list_role_editor(self):
        """`role=editor` returns the organizations where the user has a role"""
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "editor"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [org["org"] for org in response.data],
            ["editororg", "managedorg", "ownedorg"],
        )

    def test_orgs_list_role_member(self):
        """`role=member` returns every organization the user belongs to"""
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "member"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [org["org"] for org in response.data],
            ["editororg", "managedorg", "memberorg", "ownedorg"],
        )

    def test_orgs_list_role_without_org_permissions(self):
        """A role that grants nothing on an organization behaves like `member`

        A user given `readonly-no-download` in an organization is reported as
        a member of it.
        """
        self._create_orgs_with_roles()

        request = self.factory.get(
            "/", data={"role": "readonly-no-download"}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [org["org"] for org in response.data],
            ["editororg", "managedorg", "memberorg", "ownedorg"],
        )

    def test_orgs_list_role_unknown(self):
        """An unknown role is rejected"""
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "bogus"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["detail"]), "Unknown role: bogus")

    def test_orgs_list_role_below_editor(self):
        """Roles below editor return the same organizations as `role=editor`

        Every role from readonly to editor holds the same permission on an
        organization, so they cannot be told apart.
        """
        self._create_orgs_with_roles()

        request = self.factory.get("/", data={"role": "readonly"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [org["org"] for org in response.data],
            ["editororg", "managedorg", "ownedorg"],
        )

    def test_orgs_list_role_restricted(self):
        """`role` only returns organizations the user can already list"""
        self._create_orgs_with_roles()
        org_user = User.objects.get(username="ownedorg")
        org_user.is_active = False
        org_user.save()

        request = self.factory.get("/", data={"role": "owner"}, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_orgs_list_role_with_search(self):
        """`role` combines with `search`"""
        self._create_orgs_with_roles()

        # `health` alone also matches `editororg`
        request = self.factory.get(
            "/", data={"role": "manager", "search": "health"}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["ownedorg"])

    def test_orgs_list_role_with_shared_with(self):
        """`role` combines with `shared_with`"""
        self._create_orgs_with_roles()

        # carol alone is also in `editororg`
        request = self.factory.get(
            "/", data={"role": "manager", "shared_with": "carol"}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["ownedorg"])

    def test_orgs_list_role_with_pagination(self):
        """`role` combines with pagination"""
        self._create_orgs_with_roles()

        request = self.factory.get(
            "/", data={"role": "manager", "page": 2, "page_size": 1}, **self.extra
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["ownedorg"])
        self.assertEqual(
            response["Link"],
            (
                '<http://testserver/?page_size=1&role=manager>; rel="prev", '
                '<http://testserver/?page=1&page_size=1&role=manager>; rel="first"'
            ),
        )


class GetOrganizationTestCase(TestAbstractViewSet):
    """Tests for GET a single organization"""

    def setUp(self):
        super().setUp()

        self.view = OrganizationProfileViewSet.as_view({"get": "retrieve"})

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_get(self):
        """GET an organization"""
        # creating it through v1 caches what v1 returns
        self._org_create()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "url": "http://testserver/api/v2/orgs/denoinc",
                "org": "denoinc",
                "email": "mail@mail-server.org",
                "creator": "http://testserver/api/v1/users/bob",
                "metadata": {},
                "name": "Dennis",
                "encryption_keys": [],
                "city": "Denoville",
                "country": "US",
                "home_page": "deno.com",
                "twitter": "denoinc",
                "description": "",
                "require_auth": False,
                "address": "",
                "phonenumber": "",
                "num_of_submissions": 0,
                "date_modified": timezone.localtime(
                    self.organization.date_modified
                ).isoformat(),
                "current_user_role": "owner",
            },
        )

    def test_current_user_role_not_a_member(self):
        """`current_user_role` is null for a user outside the organization"""
        self._org_create()
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        self._login_user_and_profile(extra_post_data=alice_data)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["current_user_role"])

    def test_current_user_role_anonymous(self):
        """`current_user_role` is null for an anonymous user"""
        self._org_create()

        request = self.factory.get("/")
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["current_user_role"])

    def test_current_user_role_not_cached(self):
        """`current_user_role` is the role of the user making the request

        A member and a user outside the organization are served the same
        cached organization.
        """
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        add_user_to_organization(self.organization, alice)
        carol = self._create_user_profile(
            {"username": "carol", "email": "carol@localhost.com"}
        ).user

        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Token {alice.auth_token}")
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_user_role"], "member")

        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Token {carol.auth_token}")
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["current_user_role"])


class CreateOrganizationTestCase(TestAbstractViewSet):
    """Tests for POST an organization"""

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_create(self):
        """POST creates an organization"""
        view = OrganizationProfileViewSet.as_view({"post": "create"})
        data = {
            "org": "denoinc",
            "name": "Dennis",
            "email": "mail@mail-server.org",
            "city": "Denoville",
            "country": "US",
            "home_page": "deno.com",
            "twitter": "denoinc",
        }

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request)

        self.assertEqual(response.status_code, 201)
        organization = OrganizationProfile.objects.get(user__username="denoinc")
        self.assertEqual(
            response.data,
            {
                "url": "http://testserver/api/v2/orgs/denoinc",
                "org": "denoinc",
                "email": "mail@mail-server.org",
                "creator": "http://testserver/api/v1/users/bob",
                "metadata": {},
                "name": "Dennis",
                "encryption_keys": [],
                "city": "Denoville",
                "country": "US",
                "home_page": "deno.com",
                "twitter": "denoinc",
                "description": "",
                "require_auth": False,
                "address": "",
                "phonenumber": "",
                "num_of_submissions": 0,
                "date_modified": timezone.localtime(
                    organization.date_modified
                ).isoformat(),
                "current_user_role": "owner",
            },
        )

        # The organization is cached without the user specific fields
        expected_cache = {**response.data}
        del expected_cache["current_user_role"]

        self.assertEqual(
            cache.get(f"{ORG_PROFILE_V2_CACHE}denoinc-owner"), expected_cache
        )


class UpdateOrganizationTestCase(TestAbstractViewSet):
    """Tests for PATCH an organization"""

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_patch(self):
        """PATCH updates an organization"""
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"patch": "partial_update"})

        request = self.factory.patch(
            "/",
            data=json.dumps({"city": "Nairobi"}),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertEqual(
            response.data,
            {
                "url": "http://testserver/api/v2/orgs/denoinc",
                "org": "denoinc",
                "email": "mail@mail-server.org",
                "creator": "http://testserver/api/v1/users/bob",
                "metadata": {},
                "name": "Dennis",
                "encryption_keys": [],
                "city": "Nairobi",
                "country": "US",
                "home_page": "deno.com",
                "twitter": "denoinc",
                "description": "",
                "require_auth": False,
                "address": "",
                "phonenumber": "",
                "num_of_submissions": 0,
                "date_modified": timezone.localtime(
                    self.organization.date_modified
                ).isoformat(),
                "current_user_role": "owner",
            },
        )

        # The organization is cached without the user specific fields
        expected_cache = {**response.data}
        del expected_cache["current_user_role"]

        self.assertEqual(
            cache.get(f"{ORG_PROFILE_V2_CACHE}denoinc-owner"), expected_cache
        )


class DeleteOrganizationTestCase(TestAbstractViewSet):
    """Tests for DELETE an organization"""

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_delete(self):
        """DELETE removes an organization"""
        self._org_create()
        view = OrganizationProfileViewSet.as_view(
            {"delete": "destroy", "get": "retrieve"}
        )

        request = self.factory.delete("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 204)

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 404)


class OrganizationMembersTestCase(TestAbstractViewSet):
    """Tests for the members of an organization"""

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_get(self):
        """GET members returns each one once, ordered by username"""
        self._org_create()
        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user
        add_user_to_organization(self.organization, aboy)
        # an owner added this way is in both the owners and the members team
        self.profile_data["username"] = "cate"
        cate = self._create_user_profile().user
        add_user_to_organization(self.organization, cate, "owner")
        view = OrganizationProfileViewSet.as_view({"get": "members"})

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "user": "aboy",
                    "role": "member",
                    "first_name": "Bob",
                    "last_name": "erama",
                    "gravatar": aboy.profile.gravatar,
                },
                {
                    "user": "bob",
                    "role": "owner",
                    "first_name": "Bob",
                    "last_name": "erama",
                    "gravatar": self.user.profile.gravatar,
                },
                {
                    "user": "cate",
                    "role": "owner",
                    "first_name": "Bob",
                    "last_name": "erama",
                    "gravatar": cate.profile.gravatar,
                },
                {
                    "user": "denoinc",
                    "role": "owner",
                    "first_name": "Dennis",
                    "last_name": "",
                    "gravatar": self.organization.gravatar,
                },
            ],
        )

    def test_post(self):
        """POST adds a member to the organization"""
        self._org_create()
        self.profile_data["username"] = "aboy"
        self._create_user_profile()
        view = OrganizationProfileViewSet.as_view({"get": "members", "post": "members"})

        request = self.factory.post(
            "/",
            data=json.dumps({"username": "aboy"}),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(sorted(response.data), ["aboy", "denoinc"])

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(member["user"], member["role"]) for member in response.data],
            [("aboy", "member"), ("bob", "owner"), ("denoinc", "owner")],
        )

    def test_put_bad_role_query_param(self):
        """A member's `role` sent in the query string is not a list filter"""
        self._org_create()
        view = OrganizationProfileViewSet.as_view({"put": "members"})
        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user
        add_user_to_organization(self.organization, aboy)

        request = self.factory.put("/?username=aboy&role=bogus", **self.extra)
        response = view(request, user="denoinc")

        # rejected as a member's role, not as the list's `role` filter
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"role": ["Unknown role 'bogus'."]})
