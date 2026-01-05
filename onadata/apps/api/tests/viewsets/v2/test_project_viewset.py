"""Tests for onadata.apps.api.viewsets.v2.project_viewset"""

from django.core.cache import cache
from django.test import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.v2.project_viewset import ProjectViewSet
from onadata.apps.logger.models import EntityList, Project


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
        expected_data = {
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
            "users": [
                {
                    "is_org": True,
                    "metadata": {},
                    "first_name": self.organization.user.first_name,
                    "last_name": self.organization.user.last_name,
                    "user": self.organization.user.username,
                    "role": "owner",
                },
                {
                    "is_org": False,
                    "metadata": {},
                    "first_name": self.user.first_name,
                    "last_name": self.user.last_name,
                    "user": self.user.username,
                    "role": "owner",
                },
            ],
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
            "teams": [
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
            "data_views": [],
            "date_created": self.project.date_created.isoformat().replace(
                "+00:00", "Z"
            ),
            "date_modified": self.project.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
        }

        self.assertEqual(response.data, expected_data)

        # Project data is cached
        expected_cached_data = {**expected_data}
        del expected_cached_data["current_user_role"]
        self.assertEqual(
            cache.get(f"ps-project_owner-{self.project.pk}"), expected_cached_data
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
