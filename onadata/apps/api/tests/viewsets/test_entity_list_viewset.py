"""Tests for module onadata.apps.api.viewsets.entity_list_viewset"""

import json
import os
import sys

from django.conf import settings
from django.test import override_settings

from onadata.apps.api.viewsets.entity_list_viewset import EntityListViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import EntityList, Project


class GetEntityListsTestCase(TestAbstractViewSet):
    """Tests for GET all EntityLists"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "list"})

    def test_get_all(self):
        """GET all EntityLists works"""
        # Publish registration form and create "trees" EntityList dataset
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "trees_registration.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        # Publish follow up form for "trees" dataset
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "trees_follow_up.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        # Create more EntityLists explicitly
        EntityList.objects.create(name="immunization", project=self.project)
        EntityList.objects.create(name="savings", project=self.project)
        # Make request
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        first = EntityList.objects.all()[0]
        second = EntityList.objects.all()[1]
        third = EntityList.objects.all()[2]
        expected_data = [
            {
                "url": f"http://testserver/api/v1/entity-lists/{first.pk}",
                "id": first.pk,
                "name": "trees",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "num_registration_forms": 1,
                "num_follow_up_forms": 1,
            },
            {
                "url": f"http://testserver/api/v1/entity-lists/{second.pk}",
                "id": second.pk,
                "name": "immunization",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
            },
            {
                "url": f"http://testserver/api/v1/entity-lists/{third.pk}",
                "id": third.pk,
                "name": "savings",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
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
        expected_data = [
            {
                "url": f"http://testserver/api/v1/entity-lists/{first.pk}",
                "id": first.pk,
                "name": "immunization",
                "project": f"http://testserver/api/v1/projects/{public_project.pk}",
                "public": True,
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
            }
        ]
        self.assertEqual(response.data, expected_data)
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


@override_settings(TIME_ZONE="UTC")
class GetSingleEntityListTestCase(TestAbstractViewSet):
    """Tests for GET single EntityList"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "retrieve"})
        # Publish registration form and create "trees" EntityList dataset
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "trees_registration.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        # Publish follow up form for "trees" dataset
        xlsform_path = os.path.join(
            settings.PROJECT_ROOT,
            "apps",
            "main",
            "tests",
            "fixtures",
            "entities",
            "trees_follow_up.xlsx",
        )
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        self.entity_list = EntityList.objects.first()

    def test_get_entity_list(self):
        """Returns a single EntityList"""
        registration_form = self.entity_list.registration_forms.first()
        follow_up_form = self.entity_list.follow_up_forms.first()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        created_at = self.entity_list.created_at.isoformat().replace("+00:00", "Z")
        updated_at = self.entity_list.updated_at.isoformat().replace("+00:00", "Z")
        expected_data = {
            "id": self.entity_list.pk,
            "name": "trees",
            "project": f"http://testserver/api/v1/projects/{self.entity_list.pk}",
            "public": False,
            "created_at": created_at,
            "updated_at": updated_at,
            "num_registration_forms": 1,
            "num_follow_up_forms": 1,
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
