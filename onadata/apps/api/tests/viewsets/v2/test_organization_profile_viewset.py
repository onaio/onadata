"""Tests for onadata.apps.api.viewsets.v2.organization_profile_viewset"""

import json

from django.contrib.auth.models import User
from django.core.cache import cache

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_organization
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV1,
)
from onadata.apps.api.viewsets.v2.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.main.models import UserProfile


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
        """GET all organizations returns each one as the v1 list does

        Only `url` differs, as it points to the v2 endpoint, and `users`, as
        it is left out.
        """
        self._org_create()
        v1_view = OrganizationProfileViewSetV1.as_view({"get": "list"})

        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        v1_response = v1_view(self.factory.get("/", **self.extra))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.assertEqual([org["org"] for org in response.data], ["denoinc"])
        expected = []

        for org in v1_response.data:
            org = {**org, "url": None}
            del org["users"]
            expected.append(org)

        self.assertEqual([{**org, "url": None} for org in response.data], expected)

    def test_url_is_v2(self):
        """An organization's `url` points to its v2 endpoint"""
        self._org_create()

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data[0]["url"], "http://testserver/api/v2/orgs/denoinc"
        )

    def test_users_not_returned(self):
        """An organization's users are left out of the list"""
        self._org_create()

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([org["org"] for org in response.data], ["denoinc"])
        self.assertNotIn("users", response.data[0])

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

    def test_url_is_v2(self):
        """An organization's `url` points to its v2 endpoint"""
        # creating it through v1 caches what v1 returns
        self._org_create()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "http://testserver/api/v2/orgs/denoinc")

    def test_v1_url_unchanged(self):
        """Fetching an organization from v2 does not change what v1 returns"""
        self._org_create()
        cache.clear()
        v1_view = OrganizationProfileViewSetV1.as_view({"get": "retrieve"})

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        request = self.factory.get("/", **self.extra)
        response = v1_view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "http://testserver/api/v1/orgs/denoinc")

    def test_new_member_is_listed(self):
        """A member added after the organization was fetched is returned"""
        self._org_create()
        self.profile_data["username"] = "aboy"
        self._create_user_profile()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("aboy", [user["user"] for user in response.data["users"]])

        members_view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data=json.dumps({"username": "aboy"}),
            content_type="application/json",
            **self.extra,
        )
        response = members_view(request, user="denoinc")

        self.assertEqual(response.status_code, 201)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        self.assertIn("aboy", [user["user"] for user in response.data["users"]])


class OrganizationMembersTestCase(TestAbstractViewSet):
    """Tests for the members of an organization"""

    def tearDown(self):
        """Clear the cache between tests"""
        super().tearDown()
        cache.clear()

    def test_get(self):
        """GET members returns each one as the organization's `users` does"""
        self._org_create()
        self.profile_data["username"] = "aboy"
        aboy = self._create_user_profile().user
        add_user_to_organization(self.organization, aboy)
        view = OrganizationProfileViewSet.as_view({"get": "members"})

        request = self.factory.get("/", **self.extra)
        response = view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)
        members = {member["user"]: dict(member) for member in response.data}
        self.assertEqual(sorted(members), ["aboy", "bob", "denoinc"])
        gravatar = members["aboy"].pop("gravatar")
        self.assertTrue(gravatar.startswith("https://secure.gravatar.com/avatar/"))
        self.assertEqual(
            members["aboy"],
            {
                "user": "aboy",
                "role": "member",
                "first_name": "Bob",
                "last_name": "erama",
            },
        )
        self.assertEqual(members["bob"]["role"], "owner")

        retrieve_view = OrganizationProfileViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        retrieve_response = retrieve_view(request, user="denoinc")

        self.assertEqual(response.data, retrieve_response.data["users"])

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
