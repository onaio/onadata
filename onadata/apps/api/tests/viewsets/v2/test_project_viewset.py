"""Tests for onadata.apps.api.viewsets.v2.project_viewset"""

from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet as ProjectViewSetV1
from onadata.apps.api.viewsets.v2.project_viewset import ProjectViewSet
from onadata.apps.logger.models import EntityList, Project, XForm
from onadata.libs.models.share_project import ShareProject
from onadata.libs.serializers.project_serializer import PROJECT_PUBLIC_EXCLUDED_FIELDS
from onadata.libs.utils.cache_tools import (
    PROJ_OWNER_CACHE,
    PROJ_V2_OWNER_CACHE,
    PROJ_V2_PUBLIC_OWNER_CACHE,
)


@override_settings(TIME_ZONE="UTC")
class GetProjectListTestCase(TestAbstractViewSet):
    """Tests for GET list of projects"""

    def setUp(self):
        super().setUp()

        self.project = Project.objects.create(
            name="Tree Monitoring",
            organization=self.user,
            created_by=self.user,
            metadata={
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            shared=False,
        )
        self.project.tags.add("Agriculture")
        self.project.tags.add("Environment")
        self.view = ProjectViewSet.as_view({"get": "list"})

    def test_get_all(self):
        """GET all projects"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        expected_data = [
            {
                "url": f"http://testserver/api/v2/projects/{self.project.pk}",
                "projectid": self.project.pk,
                "name": "Tree Monitoring",
                "owner": f"http://testserver/api/v1/users/{self.user.username}",
                "created_by": f"http://testserver/api/v1/users/{self.user.username}",
                "metadata": {
                    "description": "Some description",
                    "location": "Naivasha, Kenya",
                    "category": "governance",
                },
                "starred": False,
                "public": False,
                "tags": ["Agriculture", "Environment"],
                "num_datasets": 0,
                "current_user_role": "owner",
                "last_submission_date": None,
                "date_created": self.project.date_created.isoformat().replace(
                    "+00:00", "Z"
                ),
                "date_modified": self.project.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
            }
        ]
        self.assertEqual(response.data, expected_data)

        self.project.shared = True
        self.project.save()

        request = self.factory.get("/")
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        public_excluded_fields = PROJECT_PUBLIC_EXCLUDED_FIELDS | {"current_user_role"}
        self.assertFalse(public_excluded_fields & set(response.data[0]))


@override_settings(TIME_ZONE="UTC")
class RetrieveProjectTestCase(TestAbstractViewSet):
    """Tests for GET single project"""

    def setUp(self):
        super().setUp()

        self._org_create()
        self.project = Project.objects.create(
            name="Tree Monitoring",
            organization=self.organization.user,
            created_by=self.user,
            metadata={
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            shared=False,
        )
        self.project.tags.add("Agriculture")
        self.project.tags.add("Environment")
        self.view = ProjectViewSet.as_view({"get": "retrieve"})

    def tearDown(self):
        cache.clear()

        super().tearDown()

    def test_retrieve_project(self):
        """GET single project"""
        xform = self._publish_registration_form(self.user, self.project)
        entity_list = EntityList.objects.get(name="trees", project=self.project)
        self.project.refresh_from_db()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        expected = {
            "url": f"http://testserver/api/v2/projects/{self.project.pk}",
            "projectid": self.project.pk,
            "name": "Tree Monitoring",
            "owner": f"http://testserver/api/v1/users/{self.organization.user.username}",
            "created_by": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "starred": False,
            "forms": [
                {
                    "name": "Trees registration",
                    "formid": xform.pk,
                    "id_string": "trees_registration",
                    "num_of_submissions": 0,
                    "downloadable": True,
                    "encrypted": False,
                    "published_by_formbuilder": None,
                    "last_submission_time": None,
                    "date_created": xform.date_created.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "url": f"http://testserver/api/v1/forms/{xform.pk}",
                    "last_updated_at": xform.last_updated_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "is_merged_dataset": False,
                    "contributes_entities_to": {
                        "id": entity_list.pk,
                        "name": "trees",
                        "is_active": True,
                    },
                    "consumes_entities_from": [],
                },
            ],
            "public": False,
            "tags": ["Agriculture", "Environment"],
            "num_datasets": 1,
            "current_user_role": "owner",
            "last_submission_date": None,
            "data_views": [],
            "date_created": self.project.date_created.isoformat().replace(
                "+00:00", "Z"
            ),
            "date_modified": self.project.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
        }
        actual = response.data.copy()

        # forms: unique by `formid`
        actual["forms"] = self.sort_by_keys(actual["forms"], "formid")
        expected["forms"] = self.sort_by_keys(expected["forms"], "formid")

        # tags simple list
        actual["tags"] = sorted(actual["tags"])
        expected["tags"] = sorted(expected["tags"])

        self.assertEqual(actual, expected)

        # Project data is cached
        expected_cache = {**response.data}
        del expected_cache["current_user_role"]
        del expected_cache["starred"]

        self.assertEqual(
            cache.get(f"{PROJ_V2_OWNER_CACHE}{self.project.pk}"), expected_cache
        )

    def test_cache_hit(self):
        """Cached data is returned if it exists"""
        # Simulate cached data
        cache.set(f"{PROJ_OWNER_CACHE}{self.project.pk}", {"name": "v1 data"})
        cache.set(
            f"{PROJ_V2_OWNER_CACHE}{self.project.pk}", {"name": "Tree Monitoring"}
        )

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "name": "Tree Monitoring",
                "starred": False,
                "current_user_role": "owner",
            },
        )

    def test_v2_update_does_not_populate_v1_detail_cache(self):
        """A v2 update cannot cache the v2 response under the v1 detail key."""
        update_view = ProjectViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"name": "Canopy Monitoring"}, **self.extra
        )
        response = update_view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["url"], f"http://testserver/api/v2/projects/{self.project.pk}"
        )
        self.assertNotIn("teams", response.data)
        self.assertIsNone(cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}"))
        self.assertEqual(
            cache.get(f"{PROJ_V2_OWNER_CACHE}{self.project.pk}")["url"],
            f"http://testserver/api/v2/projects/{self.project.pk}",
        )

        retrieve_v1 = ProjectViewSetV1.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = retrieve_v1(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["url"], f"http://testserver/api/v1/projects/{self.project.pk}"
        )
        self.assertEqual(response.data["name"], "Canopy Monitoring")
        self.assertIn("teams", response.data)
        self.assertEqual(
            cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}")["url"],
            f"http://testserver/api/v1/projects/{self.project.pk}",
        )

    def test_anon_user_public_project_fields(self):
        """Anonymous user gets the public-safe project shape."""
        self.project.shared = True
        self.project.save()

        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        public_excluded_fields = PROJECT_PUBLIC_EXCLUDED_FIELDS | {"current_user_role"}
        self.assertFalse(public_excluded_fields & set(response.data))

        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        public_excluded_fields = PROJECT_PUBLIC_EXCLUDED_FIELDS | {"current_user_role"}
        self.assertFalse(public_excluded_fields & set(response.data))

    def test_public_project_detail_cache_uses_public_and_full_variants(self):
        """Public and full project detail responses use separate cache variants."""
        self.project.shared = True
        self.project.save()
        self.project.user_stars.add(self.user)
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "readonly").save()

        # Project owner who starred the project
        self.project.refresh_from_db()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)

        expected = {
            "url": f"http://testserver/api/v2/projects/{self.project.pk}",
            "projectid": self.project.pk,
            "name": "Tree Monitoring",
            "owner": (
                f"http://testserver/api/v1/users/{self.organization.user.username}"
            ),
            "created_by": f"http://testserver/api/v1/users/{self.user.username}",
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "starred": True,
            "forms": [],
            "public": True,
            "tags": ["Agriculture", "Environment"],
            "num_datasets": 0,
            "current_user_role": "owner",
            "last_submission_date": None,
            "data_views": [],
            "date_created": self.project.date_created.isoformat().replace(
                "+00:00", "Z"
            ),
            "date_modified": self.project.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
        }
        actual = response.data.copy()
        actual["tags"] = sorted(actual["tags"])
        expected["tags"] = sorted(expected["tags"])
        self.assertEqual(actual, expected)

        # Cache holds the shared base data without user-specific fields
        expected_cache = {
            key: value
            for key, value in expected.items()
            if key not in ("starred", "current_user_role")
        }
        full_cache = cache.get(f"{PROJ_V2_OWNER_CACHE}{self.project.pk}")
        actual_cache = full_cache.copy()
        actual_cache["tags"] = sorted(actual_cache["tags"])
        self.assertEqual(actual_cache, expected_cache)

        # Alice with readonly who did not star the project
        request = self.factory.get(
            "/",
            **{"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"},
        )
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        expected_alice = {
            **expected,
            "starred": False,
            "current_user_role": "readonly",
        }
        actual = response.data.copy()
        actual["tags"] = sorted(actual["tags"])
        expected_alice["tags"] = sorted(expected_alice["tags"])
        self.assertEqual(actual, expected_alice)

        # Anonymous user: public variant, admin and user-specific fields omitted
        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)

        excluded_fields = PROJECT_PUBLIC_EXCLUDED_FIELDS | {
            "starred",
            "current_user_role",
        }
        expected_public = {
            key: value for key, value in expected.items() if key not in excluded_fields
        }
        actual = response.data.copy()
        actual["tags"] = sorted(actual["tags"])
        expected_public["tags"] = sorted(expected_public["tags"])
        self.assertEqual(actual, expected_public)

        public_cache = cache.get(f"{PROJ_V2_PUBLIC_OWNER_CACHE}{self.project.pk}")
        actual_public_cache = public_cache.copy()
        actual_public_cache["tags"] = sorted(actual_public_cache["tags"])
        self.assertEqual(actual_public_cache, expected_public)

        cache.clear()

        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        actual = response.data.copy()
        actual["tags"] = sorted(actual["tags"])
        self.assertEqual(actual, expected_public)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["starred"])
        self.assertIn("owner", response.data)
        self.assertIn("current_user_role", response.data)
        full_cache = cache.get(f"{PROJ_V2_OWNER_CACHE}{self.project.pk}")
        self.assertIsNotNone(full_cache)
        self.assertIn("owner", full_cache)
        self.assertNotIn("starred", full_cache)


@override_settings(TIME_ZONE="UTC")
class GetProjectUsersTestCase(TestAbstractViewSet):
    """Tests for GET project users"""

    def setUp(self):
        super().setUp()

        self.project = Project.objects.create(
            name="Tree Monitoring",
            organization=self.user,
            created_by=self.user,
            shared=False,
        )
        self.view = ProjectViewSet.as_view({"get": "users"})

    def tearDown(self):
        cache.clear()

        super().tearDown()

    def test_owner_can_view_users(self):
        """Project owner can view the list of users with access"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "is_org": False,
                    "metadata": {},
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                    "user": self.user.username,
                    "role": "owner",
                },
            ],
        )

    def test_manager_can_view_users(self):
        """A project manager can view the list of users with access"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "manager").save()
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        usernames = sorted(entry["user"] for entry in response.data)
        self.assertEqual(usernames, ["alice", self.user.username])

    def test_member_can_view_users(self):
        """A read-only member can view the list of users with access"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "readonly").save()
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        usernames = sorted(entry["user"] for entry in response.data)
        self.assertEqual(usernames, ["alice", self.user.username])

    def test_inactive_users_excluded(self):
        """Inactive users are not listed among the project users"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "readonly").save()

        # alice is listed while active
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        usernames = sorted(entry["user"] for entry in response.data)
        self.assertEqual(usernames, ["alice", self.user.username])

        # deactivate alice
        alice_profile.user.is_active = False
        alice_profile.user.save()

        # simulate the cached permissions list expiring
        cache.clear()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)
        usernames = [entry["user"] for entry in response.data]
        self.assertNotIn("alice", usernames)
        self.assertEqual(usernames, [self.user.username])

    def test_non_member_denied(self):
        """A user with no role on the project cannot view the users"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_denied(self):
        """An anonymous user cannot view the list of users"""
        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_non_member_denied_public_project(self):
        """A non-member cannot view the users of a public project

        A public project is returned by the project filter backend regardless
        of membership, so the explicit member check in ProjectPermissions is
        what keeps the users list members-only here.
        """
        self.project.shared = True
        self.project.save()
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 403)


@override_settings(TIME_ZONE="UTC")
class GetProjectTeamsTestCase(TestAbstractViewSet):
    """Tests for GET project teams"""

    def setUp(self):
        super().setUp()

        self._org_create()
        self.project = Project.objects.create(
            name="Tree Monitoring",
            organization=self.organization.user,
            created_by=self.user,
            shared=False,
        )
        self.view = ProjectViewSet.as_view({"get": "teams"})

    def tearDown(self):
        cache.clear()

        super().tearDown()

    def test_owner_can_view_teams(self):
        """Project owner can view the list of teams with access"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.sort_by_keys(response.data, "name"),
            [
                {
                    "name": "denoinc#Owners",
                    "role": "owner",
                    "users": [self.user.username],
                },
                {
                    "name": "denoinc#members",
                    "role": None,
                    "users": [self.organization.user.username],
                },
            ],
        )

    def test_manager_can_view_teams(self):
        """A project manager can view the list of teams with access"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "manager").save()
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        team_names = sorted(entry["name"] for entry in response.data)
        self.assertEqual(team_names, ["denoinc#Owners", "denoinc#members"])

    def test_member_can_view_teams(self):
        """A read-only member can view the list of teams with access"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        ShareProject(self.project, "alice", "readonly").save()
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        team_names = sorted(entry["name"] for entry in response.data)
        self.assertEqual(team_names, ["denoinc#Owners", "denoinc#members"])

    def test_non_member_denied(self):
        """A user with no role on the project cannot view the teams"""
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_denied(self):
        """An anonymous user cannot view the list of teams"""
        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 404)

    def test_non_member_denied_public_project(self):
        """A non-member cannot view the teams of a public project

        A public project is returned by the project filter backend regardless
        of membership, so the explicit member check in ProjectPermissions is
        what keeps the teams list members-only here.
        """
        self.project.shared = True
        self.project.save()
        alice_profile = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        )
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 403)


class ProjectListFilterTestBase(TestAbstractViewSet):
    """Shared helpers for the v2 project list filter/sort test cases."""

    def setUp(self):
        super().setUp()
        self.view = ProjectViewSet.as_view({"get": "list"})

    def _list(self, params, extra=None):
        """GET the project list with query params (defaults to self.extra auth).

        Pass ``extra={}`` for an unauthenticated (anonymous) request.
        """
        if extra is None:
            extra = self.extra
        return self.view(self.factory.get("/", params, **extra))

    def _names(self, response, sort=True):
        names = [project["name"] for project in response.data]
        return sorted(names) if sort else names


@override_settings(TIME_ZONE="UTC")
class ProjectSearchTestCase(ProjectListFilterTestBase):
    """?search= matches project name and owner username."""

    def setUp(self):
        super().setUp()
        self.alpha = Project.objects.create(
            name="Rainfall Survey",
            organization=self.user,
            created_by=self.user,
        )
        self.beta = Project.objects.create(
            name="Household Census",
            organization=self.user,
            created_by=self.user,
        )

    def test_search_by_name(self):
        """?search= matches projects by name, case-insensitively."""
        response = self._list({"search": "rain"})
        self.assertEqual(self._names(response), ["Rainfall Survey"])

    def test_search_by_owner_username(self):
        """?search= matches projects by the owner's username."""
        response = self._list({"search": self.user.username})
        self.assertEqual(self._names(response), ["Household Census", "Rainfall Survey"])

    def test_search_combines_with_ordering(self):
        """?search= and ?ordering= can be combined in a single request."""
        response = self._list({"search": self.user.username, "ordering": "-name"})
        self.assertEqual(
            self._names(response, sort=False),
            ["Rainfall Survey", "Household Census"],
        )


@override_settings(TIME_ZONE="UTC")
class ProjectOrderingTestCase(ProjectListFilterTestBase):
    """?ordering= sorts by name / created."""

    def setUp(self):
        super().setUp()
        self.banana = Project.objects.create(
            name="Banana", organization=self.user, created_by=self.user
        )
        self.apple = Project.objects.create(
            name="Apple", organization=self.user, created_by=self.user
        )
        self.cherry = Project.objects.create(
            name="Cherry", organization=self.user, created_by=self.user
        )

    def test_order_by_name_asc(self):
        """?ordering=name sorts projects alphabetically."""
        response = self._list({"ordering": "name"})
        self.assertEqual(
            self._names(response, sort=False), ["Apple", "Banana", "Cherry"]
        )

    def test_order_by_name_desc(self):
        """?ordering=-name sorts projects reverse-alphabetically."""
        response = self._list({"ordering": "-name"})
        self.assertEqual(
            self._names(response, sort=False), ["Cherry", "Banana", "Apple"]
        )

    def test_order_by_created_asc(self):
        """?ordering=date_created sorts the oldest-created project first."""
        response = self._list({"ordering": "date_created"})
        self.assertEqual(
            self._names(response, sort=False), ["Banana", "Apple", "Cherry"]
        )


@override_settings(TIME_ZONE="UTC")
class ProjectOrderingDerivedTestCase(ProjectListFilterTestBase):
    """?ordering=last_submission and ?ordering=category."""

    def setUp(self):
        super().setUp()
        self.p_agri = Project.objects.create(
            name="Agri",
            organization=self.user,
            created_by=self.user,
            metadata={"category": "agriculture"},
        )
        self.p_gov = Project.objects.create(
            name="Gov",
            organization=self.user,
            created_by=self.user,
            metadata={"category": "governance"},
        )

    def _make_form(self, project, id_string, last_submission_time):
        """Create a minimal XForm on *project* with a fixed last submission time."""
        xml = (
            '<?xml version="1.0"?><h:html xmlns="http://www.w3.org/2002/xforms" '
            'xmlns:h="http://www.w3.org/1999/xhtml"><h:head>'
            f"<h:title>{id_string}</h:title><model><instance>"
            f'<data id="{id_string}"><name/></data>'
            "</instance></model></h:head><h:body/></h:html>"
        )
        # sms_id_string is supplied so save() doesn't derive it from the
        # pyxform JSON, which this minimal fixture doesn't carry.
        xform = XForm.objects.create(
            xml=xml,
            user=self.user,
            project=project,
            json={},
            sms_id_string=id_string,
        )
        XForm.objects.filter(pk=xform.pk).update(
            last_submission_time=last_submission_time
        )
        return xform

    def test_order_by_category_asc(self):
        """?ordering=metadata__category sorts by the JSON category value."""
        response = self._list({"ordering": "metadata__category"})
        self.assertEqual(self._names(response, sort=False), ["Agri", "Gov"])

    def test_order_by_last_submission_asc(self):
        """?ordering=last_submission_date puts the least recently submitted-to
        project first."""
        now = timezone.now()
        self._make_form(self.p_agri, "agri_form", now - timedelta(days=2))
        self._make_form(self.p_gov, "gov_form", now - timedelta(days=1))
        response = self._list({"ordering": "last_submission_date"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response, sort=False), ["Agri", "Gov"])

    def test_order_by_last_submission_desc(self):
        """?ordering=-last_submission_date puts the most recently submitted-to
        project first."""
        now = timezone.now()
        self._make_form(self.p_agri, "agri_form", now - timedelta(days=2))
        self._make_form(self.p_gov, "gov_form", now - timedelta(days=1))
        response = self._list({"ordering": "-last_submission_date"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response, sort=False), ["Gov", "Agri"])


@override_settings(TIME_ZONE="UTC")
class ProjectSharedFilterTestCase(ProjectListFilterTestBase):
    """?shared= filters public/private projects."""

    def setUp(self):
        super().setUp()
        self.public = Project.objects.create(
            name="Public One", organization=self.user, created_by=self.user, shared=True
        )
        self.private = Project.objects.create(
            name="Private One",
            organization=self.user,
            created_by=self.user,
            shared=False,
        )

    def test_filter_shared_true(self):
        """?shared=true returns only public projects."""
        response = self._list({"shared": "true"})
        self.assertEqual(self._names(response), ["Public One"])

    def test_filter_shared_false(self):
        """?shared=false returns only private projects."""
        response = self._list({"shared": "false"})
        self.assertEqual(self._names(response), ["Private One"])


@override_settings(TIME_ZONE="UTC")
class ProjectStarredFilterTestCase(ProjectListFilterTestBase):
    """?starred= filters by the requesting user's stars."""

    def setUp(self):
        super().setUp()
        self.starred = Project.objects.create(
            name="Starred One", organization=self.user, created_by=self.user
        )
        self.plain = Project.objects.create(
            name="Plain One", organization=self.user, created_by=self.user
        )
        self.starred.user_stars.add(self.user)

    def test_filter_starred_true(self):
        """?starred=true returns only the requesting user's starred projects."""
        response = self._list({"starred": "true"})
        self.assertEqual(self._names(response), ["Starred One"])

    def test_filter_starred_false(self):
        """?starred=false returns only projects the user has not starred."""
        response = self._list({"starred": "false"})
        self.assertEqual(self._names(response), ["Plain One"])

    def test_filter_starred_anonymous(self):
        """An anonymous ?starred= request is handled gracefully, not a 500."""
        Project.objects.filter(pk__in=[self.starred.pk, self.plain.pk]).update(
            shared=True
        )
        response = self._list({"starred": "true"}, extra={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response), [])
        response = self._list({"starred": "false"}, extra={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response), ["Plain One", "Starred One"])

    def test_filter_starred_invalid_value(self):
        """A ?starred= value other than true/false is a 400, not silently false."""
        response = self._list({"starred": "banana"})
        self.assertEqual(response.status_code, 400)


@override_settings(TIME_ZONE="UTC")
class ProjectRoleFilterTestCase(ProjectListFilterTestBase):
    """?role= returns projects where the requesting user's role is in the set."""

    def setUp(self):
        super().setUp()
        self.member = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        self.member_extra = {"HTTP_AUTHORIZATION": f"Token {self.member.auth_token}"}

        self.owner_p = self._make_shared_project("Owner Proj", "owner")
        self.manager_p = self._make_shared_project("Manager Proj", "manager")
        self.editor_p = self._make_shared_project("Editor Proj", "editor")
        self.readonly_p = self._make_shared_project("Readonly Proj", "readonly")

    def _make_shared_project(self, name, role):
        proj = Project.objects.create(
            name=name, organization=self.user, created_by=self.user
        )
        ShareProject(proj, "alice", role).save()
        return proj

    def test_role_owner_only(self):
        """?role=owner returns only projects where the user is an owner."""
        response = self._list({"role": "owner"}, extra=self.member_extra)
        self.assertEqual(self._names(response), ["Owner Proj"])

    def test_role_owner_or_manager(self):
        """?role=owner,manager returns manager-and-above projects."""
        response = self._list({"role": "owner,manager"}, extra=self.member_extra)
        self.assertEqual(self._names(response), ["Manager Proj", "Owner Proj"])

    def test_role_editor_includes_higher_roles(self):
        """?role=editor means editor-and-above: manager and owner projects
        are included because those roles hold every editor permission."""
        response = self._list({"role": "editor"}, extra=self.member_extra)
        self.assertEqual(
            self._names(response), ["Editor Proj", "Manager Proj", "Owner Proj"]
        )

    def test_role_unknown_is_rejected(self):
        """An unknown role name is a 400, not a silent no-op."""
        response = self._list({"role": "bogus"}, extra=self.member_extra)
        self.assertEqual(response.status_code, 400)

    def test_user_not_shared_to_any_project(self):
        """A user shared into no projects gets an empty list, not a 4xx."""
        not_shared_user = self._create_user_profile(
            {"username": "carol", "email": "carol@localhost.com"}
        ).user
        not_shared_user_extra = {
            "HTTP_AUTHORIZATION": f"Token {not_shared_user.auth_token}"
        }
        response = self._list({"role": "owner"}, extra=not_shared_user_extra)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
