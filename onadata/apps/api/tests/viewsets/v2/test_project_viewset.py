"""Tests for onadata.apps.api.viewsets.v2.project_viewset"""

from django.core.cache import cache
from django.test import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.v2.project_viewset import ProjectViewSet
from onadata.apps.logger.models import EntityList, Project
from onadata.libs.models.share_project import ShareProject


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

        self.assertEqual(
            cache.get(f"ps-project_owner-{self.project.pk}"), expected_cache
        )

    def test_cache_hit(self):
        """Cached data is returned if it exists"""
        # Simulate cached data
        cache.set(f"ps-project_owner-{self.project.pk}", {"name": "Tree Monitoring"})

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, {"name": "Tree Monitoring", "current_user_role": "owner"}
        )

    def test_anon_user_current_user_role(self):
        """Anonymous user has no current user role"""
        self.project.shared = True
        self.project.save()

        request = self.factory.get("/")
        response = self.view(request, pk=self.project.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["current_user_role"])


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
