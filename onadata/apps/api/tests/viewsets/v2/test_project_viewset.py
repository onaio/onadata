"""Tests for onadata.apps.api.viewsets.v2.project_viewset"""

from django.core.cache import cache
from django.test import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.project_viewset import (
    ProjectViewSet as ProjectViewSetV1,
)
from onadata.apps.api.viewsets.v2.project_viewset import ProjectViewSet
from onadata.apps.logger.models import EntityList, Project
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


@override_settings(TIME_ZONE="UTC")
class ProjectSearchTestCase(TestAbstractViewSet):
    """?search= matches project name and owner username."""

    def setUp(self):
        super().setUp()
        self.alpha = Project.objects.create(
            name="Rainfall Survey", organization=self.user, created_by=self.user,
        )
        self.beta = Project.objects.create(
            name="Household Census", organization=self.user, created_by=self.user,
        )
        self.view = ProjectViewSet.as_view({"get": "list"})

    def _names(self, response):
        return sorted(p["name"] for p in response.data)

    def test_search_by_name(self):
        request = self.factory.get("/", {"search": "rain"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response), ["Rainfall Survey"])

    def test_search_by_owner_username(self):
        # self.user.username is the owner of both projects.
        request = self.factory.get("/", {"search": self.user.username}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._names(response), ["Household Census", "Rainfall Survey"])

    def test_search_no_match_returns_empty(self):
        request = self.factory.get("/", {"search": "zzznotreal"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


@override_settings(TIME_ZONE="UTC")
class ProjectOrderingTestCase(TestAbstractViewSet):
    """?ordering= sorts by name / created."""

    def setUp(self):
        super().setUp()
        # Created oldest → newest: Banana, Apple, Cherry
        self.banana = Project.objects.create(
            name="Banana", organization=self.user, created_by=self.user)
        self.apple = Project.objects.create(
            name="Apple", organization=self.user, created_by=self.user)
        self.cherry = Project.objects.create(
            name="Cherry", organization=self.user, created_by=self.user)
        self.view = ProjectViewSet.as_view({"get": "list"})

    def _names(self, response):
        return [p["name"] for p in response.data]

    def test_order_by_name_asc(self):
        request = self.factory.get("/", {"ordering": "name"}, **self.extra)
        response = self.view(request)
        self.assertEqual(self._names(response), ["Apple", "Banana", "Cherry"])

    def test_order_by_created_desc(self):
        request = self.factory.get("/", {"ordering": "-date_created"}, **self.extra)
        response = self.view(request)
        self.assertEqual(self._names(response), ["Cherry", "Apple", "Banana"])

    def test_order_by_created_asc(self):
        request = self.factory.get("/", {"ordering": "date_created"}, **self.extra)
        response = self.view(request)
        # Ascending date_created differs from the default -date_created order,
        # so this fails if OrderingFilter/ordering_fields is broken or dropped.
        self.assertEqual(self._names(response), ["Banana", "Apple", "Cherry"])


@override_settings(TIME_ZONE="UTC")
class ProjectOrderingDerivedTestCase(TestAbstractViewSet):
    """?ordering=last_submission and ?ordering=category."""

    def setUp(self):
        super().setUp()
        # Create Agri before Gov (oldest -> newest) so the default queryset
        # ordering (-date_created) puts Gov first. This decouples the
        # ?ordering=metadata__category assertion below from the fallback
        # ordering used when the field isn't recognised — without this,
        # the test would pass even before ordering_fields is extended.
        self.p_agri = Project.objects.create(
            name="Agri", organization=self.user, created_by=self.user,
            metadata={"category": "agriculture"})
        self.p_gov = Project.objects.create(
            name="Gov", organization=self.user, created_by=self.user,
            metadata={"category": "governance"})
        self.view = ProjectViewSet.as_view({"get": "list"})

    def _names(self, response):
        return [p["name"] for p in response.data]

    def test_order_by_category_asc(self):
        request = self.factory.get(
            "/", {"ordering": "metadata__category"}, **self.extra
        )
        response = self.view(request)
        # agriculture < governance
        self.assertEqual(self._names(response), ["Agri", "Gov"])

    def test_order_by_last_submission_desc(self):
        request = self.factory.get(
            "/", {"ordering": "-last_submission_date"}, **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        # No submissions on either → both null; assert the ordering param is
        # accepted (200) and returns both projects rather than erroring.
        self.assertEqual(sorted(self._names(response)), ["Agri", "Gov"])


@override_settings(TIME_ZONE="UTC")
class ProjectSharedFilterTestCase(TestAbstractViewSet):
    """?shared= filters public/private projects."""

    def setUp(self):
        super().setUp()
        self.public = Project.objects.create(
            name="Public One", organization=self.user, created_by=self.user,
            shared=True)
        self.private = Project.objects.create(
            name="Private One", organization=self.user, created_by=self.user,
            shared=False)
        self.view = ProjectViewSet.as_view({"get": "list"})

    def _names(self, response):
        return sorted(p["name"] for p in response.data)

    def test_filter_shared_true(self):
        request = self.factory.get("/", {"shared": "true"}, **self.extra)
        response = self.view(request)
        self.assertEqual(self._names(response), ["Public One"])

    def test_filter_shared_false(self):
        request = self.factory.get("/", {"shared": "false"}, **self.extra)
        response = self.view(request)
        self.assertEqual(self._names(response), ["Private One"])
