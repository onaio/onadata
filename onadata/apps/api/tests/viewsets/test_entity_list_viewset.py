"""Tests for module onadata.apps.api.viewsets.entity_list_viewset"""

import json
import os
import sys

from django.conf import settings
from django.test import override_settings

from onadata.apps.api.viewsets.entity_list_viewset import EntityListViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import Entity, EntityList, Project
from onadata.libs.models.share_project import ShareProject


class GetEntityListsTestCase(TestAbstractViewSet):
    """Tests for GET all EntityLists"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "list"})

    @override_settings(TIME_ZONE="UTC")
    def test_get_all(self):
        """GET all EntityLists works"""
        # Publish registration form and create "trees" EntityList dataset
        self._publish_registration_form()
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form()
        # Make submission on tree_registration form
        submission_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "instances",
            "trees_registration.xml",
        )
        self._make_submission(submission_path)
        # Create more EntityLists explicitly
        EntityList.objects.create(name="immunization", project=self.project)
        EntityList.objects.create(name="savings", project=self.project)
        qs = EntityList.objects.all().order_by("pk")
        first = qs[0]
        second = qs[1]
        third = qs[2]
        # Make request
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        expected_data = [
            {
                "url": f"http://testserver/api/v1/entity-lists/{first.pk}",
                "id": first.pk,
                "name": "trees",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "created_at": first.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": first.updated_at.isoformat().replace("+00:00", "Z"),
                "num_registration_forms": 1,
                "num_follow_up_forms": 1,
                "num_entities": 1,
            },
            {
                "url": f"http://testserver/api/v1/entity-lists/{second.pk}",
                "id": second.pk,
                "name": "immunization",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "created_at": second.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": second.updated_at.isoformat().replace("+00:00", "Z"),
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
                "num_entities": 0,
            },
            {
                "url": f"http://testserver/api/v1/entity-lists/{third.pk}",
                "id": third.pk,
                "name": "savings",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "created_at": third.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": third.updated_at.isoformat().replace("+00:00", "Z"),
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
                "num_entities": 0,
            },
        ]
        self.assertEqual(response.data, expected_data)

    def test_anonymous_user(self):
        """Anonymous user can only view EntityLists under public projects"""
        # Create public project
        public_project = Project.objects.create(
            name="public",
            shared=True,
            created_by=self.user,
            organization=self.user,
        )
        # Create private project
        private_project = Project.objects.create(
            name="private",
            shared=False,
            created_by=self.user,
            organization=self.user,
        )
        # Create EntityList explicitly
        EntityList.objects.create(name="immunization", project=public_project)
        EntityList.objects.create(name="savings", project=private_project)
        # Make request as anonymous user
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.assertEqual(len(response.data), 1)
        first = EntityList.objects.all()[0]
        self.assertEqual(response.data[0]["id"], first.pk)
        # Logged in user is able to view all
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.assertEqual(len(response.data), 2)

    def test_pagination(self):
        """Pagination works"""
        self._project_create()
        EntityList.objects.create(name="dataset_1", project=self.project)
        EntityList.objects.create(name="dataset_2", project=self.project)
        request = self.factory.get("/", data={"page": 1, "page_size": 1}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_filtering_by_project(self):
        """Filter by project id works"""
        self._project_create()
        project_2 = Project.objects.create(
            name="Other project",
            created_by=self.user,
            organization=self.user,
        )
        EntityList.objects.create(name="dataset_1", project=self.project)
        EntityList.objects.create(name="dataset_2", project=project_2)
        request = self.factory.get("/", data={"project": project_2.pk}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "dataset_2")


@override_settings(TIME_ZONE="UTC")
class GetSingleEntityListTestCase(TestAbstractViewSet):
    """Tests for GET single EntityList"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "retrieve"})
        # Publish registration form and create "trees" EntityList dataset
        self._publish_registration_form()
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form()
        self.entity_list = EntityList.objects.first()
        # Make submission on tree_registration form
        submission_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "instances",
            "trees_registration.xml",
        )
        self._make_submission(submission_path)

    def test_get_entity_list(self):
        """Returns a single EntityList"""
        registration_form = self.entity_list.registration_forms.first()
        follow_up_form = self.entity_list.follow_up_forms.first()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.entity_list.refresh_from_db()
        created_at = self.entity_list.created_at.isoformat().replace("+00:00", "Z")
        updated_at = self.entity_list.updated_at.isoformat().replace("+00:00", "Z")
        expected_data = {
            "id": self.entity_list.pk,
            "name": "trees",
            "project": f"http://testserver/api/v1/projects/{self.project.pk}",
            "public": False,
            "created_at": created_at,
            "updated_at": updated_at,
            "num_registration_forms": 1,
            "num_follow_up_forms": 1,
            "num_entities": 1,
            "registration_forms": [
                {
                    "title": "Trees registration",
                    "xform": f"http://testserver/api/v1/forms/{registration_form.xform.pk}",
                    "id_string": "trees_registration",
                    "save_to": [
                        "geometry",
                        "species",
                        "circumference_cm",
                    ],
                },
            ],
            "follow_up_forms": [
                {
                    "title": "Trees follow-up",
                    "xform": f"http://testserver/api/v1/forms/{follow_up_form.xform.pk}",
                    "id_string": "trees_follow_up",
                }
            ],
        }
        self.assertEqual(json.dumps(response.data), json.dumps(expected_data))

    def test_anonymous_user(self):
        """Anonymous user cannot view a private EntityList"""
        # Anonymous user cannot view private EntityList
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)
        # Anonymous user can view public EntityList
        self.project.shared = True
        self.project.save()
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)

    def test_does_not_exist(self):
        """Invalid EntityList is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_shared_project(self):
        """A user can view a project shared with them"""
        alice_data = {
            "username": "alice",
            "email": "aclie@example.com",
            "password1": "password12345",
            "password2": "password12345",
            "first_name": "Alice",
            "last_name": "Hughes",
        }
        alice_profile = self._create_user_profile(alice_data)
        # Share project with Alice
        ShareProject(self.project, "alice", "readonly-no-download")
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}
        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)


class GetEntitiesTestCase(TestAbstractViewSet):
    """Tests for GET Entities"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "entities"})
        # Publish registration form and create "trees" EntityList dataset
        self._publish_registration_form()
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form()
        # Make submissions which will then create Entities
        paths = [
            os.path.join(
                self.main_directory,
                "fixtures",
                "entities",
                "instances",
                "trees_registration.xml",
            ),
            os.path.join(
                self.main_directory,
                "fixtures",
                "entities",
                "instances",
                "trees_registration_2.xml",
            ),
        ]

        for path in paths:
            self._make_submission(path)

        self.entity_list = EntityList.objects.first()
        entity_qs = Entity.objects.all().order_by("pk")
        self.expected_data = [
            {
                "formhub/uuid": "d156a2dce4c34751af57f21ef5c4e6cc",
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/instanceID": "uuid:9d3f042e-cfec-4d2a-8b5b-212e3b04802b",
                "meta/instanceName": "300cm purpleheart",
                "meta/entity/label": "300cm purpleheart",
                "_xform_id_string": "trees_registration",
                "_version": "2022110901",
                "_id": entity_qs[0].pk,
            },
            {
                "formhub/uuid": "d156a2dce4c34751af57f21ef5c4e6cc",
                "geometry": "-1.305796 36.791849 0 0",
                "species": "wallaba",
                "circumference_cm": 100,
                "intake_notes": "Looks malnourished",
                "meta/instanceID": "uuid:648e4106-2224-4bd7-8bf9-859102fc6fae",
                "meta/instanceName": "100cm wallaba",
                "meta/entity/label": "100cm wallaba",
                "_xform_id_string": "trees_registration",
                "_version": "2022110901",
                "_id": entity_qs[1].pk,
            },
        ]

    def test_get_all(self):
        """All Entities are returned"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.expected_data)
        self.assertIsNotNone(response.get("Cache-Control"))

    def test_anonymous_user(self):
        """Anonymous user cannot view Entities for a private EntityList"""
        # Anonymous user cannot view private EntityList
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)
        # Anonymous user can view public EntityList
        self.project.shared = True
        self.project.save()
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.expected_data)

    def test_shared_project(self):
        """A user can view Entities for a project shared with them"""
        alice_data = {
            "username": "alice",
            "email": "aclie@example.com",
            "password1": "password12345",
            "password2": "password12345",
            "first_name": "Alice",
            "last_name": "Hughes",
        }
        alice_profile = self._create_user_profile(alice_data)
        # Share project with Alice
        ShareProject(self.project, "alice", "readonly-no-download")
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}
        request = self.factory.get("/", **extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.expected_data)

    def test_pagination(self):
        """Pagination works"""
        request = self.factory.get("/", data={"page": 1, "page_size": 1}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["meta/entity/label"], "300cm purpleheart")
