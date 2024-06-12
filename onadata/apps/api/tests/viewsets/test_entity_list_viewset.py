"""Tests for module onadata.apps.api.viewsets.entity_list_viewset"""

import json
import sys
from datetime import datetime

from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from onadata.apps.api.viewsets.entity_list_viewset import EntityListViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import Entity, EntityHistory, EntityList, Project
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import ROLES


class GetEntityListsTestCase(TestAbstractViewSet):
    """Tests for GET all EntityLists"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "list"})

    @override_settings(TIME_ZONE="UTC")
    def test_get_all(self):
        """GET all EntityLists works"""
        # Publish registration form and create "trees" EntityList dataset
        self._publish_registration_form(self.user)
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form(self.user)
        # Create Entity for trees EntityList
        trees_entity_list = EntityList.objects.get(name="trees")
        Entity.objects.create(
            entity_list=trees_entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        trees_entity_list.num_entities = 1
        trees_entity_list.save()
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
                "url": f"http://testserver/api/v2/entity-lists/{first.pk}",
                "id": first.pk,
                "name": "trees",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "date_created": first.date_created.isoformat().replace("+00:00", "Z"),
                "date_modified": first.date_modified.isoformat().replace("+00:00", "Z"),
                "num_registration_forms": 1,
                "num_follow_up_forms": 1,
                "num_entities": 1,
            },
            {
                "url": f"http://testserver/api/v2/entity-lists/{second.pk}",
                "id": second.pk,
                "name": "immunization",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "date_created": second.date_created.isoformat().replace("+00:00", "Z"),
                "date_modified": second.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
                "num_registration_forms": 0,
                "num_follow_up_forms": 0,
                "num_entities": 0,
            },
            {
                "url": f"http://testserver/api/v2/entity-lists/{third.pk}",
                "id": third.pk,
                "name": "savings",
                "project": f"http://testserver/api/v1/projects/{self.project.pk}",
                "public": False,
                "date_created": third.date_created.isoformat().replace("+00:00", "Z"),
                "date_modified": third.date_modified.isoformat().replace("+00:00", "Z"),
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
        self._publish_registration_form(self.user)
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form(self.user)
        self.entity_list = EntityList.objects.first()
        # Create Entity for trees EntityList
        trees_entity_list = EntityList.objects.get(name="trees")
        Entity.objects.create(
            entity_list=trees_entity_list,
            json={
                "species": "purpleheart",
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )
        trees_entity_list.num_entities = 1
        trees_entity_list.save()

    def test_get_entity_list(self):
        """Returns a single EntityList"""
        registration_form = self.entity_list.registration_forms.first()
        follow_up_form = self.entity_list.follow_up_forms.first()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.entity_list.refresh_from_db()
        date_created = self.entity_list.date_created.isoformat().replace("+00:00", "Z")
        date_modified = self.entity_list.date_modified.isoformat().replace(
            "+00:00", "Z"
        )
        expected_data = {
            "id": self.entity_list.pk,
            "name": "trees",
            "project": f"http://testserver/api/v1/projects/{self.project.pk}",
            "public": False,
            "date_created": date_created,
            "date_modified": date_modified,
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
        ShareProject(self.project, "alice", "readonly-no-download").save()
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
        self._publish_registration_form(self.user)
        # Publish follow up form for "trees" dataset
        self._publish_follow_up_form(self.user)
        # Create Entity for trees EntityList
        self.entity_list = EntityList.objects.get(name="trees")
        Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        ),
        Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.305796 36.791849 0 0",
                "species": "wallaba",
                "circumference_cm": 100,
                "intake_notes": "Looks malnourished",
                "meta/entity/label": "100cm wallaba",
            },
            uuid="517185b4-bc06-450c-a6ce-44605dec5480",
        )
        self.entity_list.num_entities = 2
        self.entity_list.save()
        entity_qs = Entity.objects.all().order_by("pk")
        self.expected_data = [
            {
                "id": entity_qs[0].pk,
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            {
                "id": entity_qs[1].pk,
                "geometry": "-1.305796 36.791849 0 0",
                "species": "wallaba",
                "circumference_cm": 100,
                "intake_notes": "Looks malnourished",
                "meta/entity/label": "100cm wallaba",
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
        ShareProject(self.project, "alice", "readonly-no-download").save()
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

    def test_deleted_ignored(self):
        """Deleted Entities are ignored"""
        entity_qs = Entity.objects.all().order_by("pk")
        entity_first = entity_qs.first()
        entity_first.deleted_at = timezone.now()
        entity_first.save()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [self.expected_data[-1]])
        self.assertIsNotNone(response.get("Cache-Control"))


class UpdateEntityTestCase(TestAbstractViewSet):
    """Tests for updating a single Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view(
            {"put": "entities", "patch": "entities"},
        )

        # Simulate existing Entity
        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees")
        self.entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

    def test_updating_entity(self):
        """Updating an Entity works"""
        data = {
            "label": "30cm mora",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": 30,
            },
        }
        request = self.factory.put("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            "geometry": "-1.286805 36.772845 0 0",
            "species": "mora",
            "circumference_cm": 30,
            "meta/entity/label": "30cm mora",
        }
        self.assertDictEqual(response.data, expected_data)
        self.assertEqual(EntityHistory.objects.count(), 1)
        history = EntityHistory.objects.first()
        self.assertEqual(history.entity, self.entity)
        self.assertIsNone(history.registration_form)
        self.assertIsNone(history.instance)
        self.assertIsNone(history.xml)
        self.assertIsNone(history.form_version)
        self.assertDictEqual(history.json, expected_data)
        self.assertEqual(history.created_by, self.user)

    def test_invalid_entity(self):
        """Invalid Entity is handled"""
        request = self.factory.put("/", data={}, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_patch_label(self):
        """Patching label only works"""
        data = {"label": "Patched label"}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            **self.entity.json,
            "meta/entity/label": "Patched label",
        }
        self.assertDictEqual(response.data, expected_data)

    def test_patch_data(self):
        """Patch data only works"""
        data = {"data": {"species": "mora"}}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            **self.entity.json,
            "species": "mora",
        }
        self.assertDictEqual(response.data, expected_data)

    def test_label_empty(self):
        """Label must be a non-empty string"""
        data = {"label": ""}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)

    def test_unset_property(self):
        """Unsetting a property value works"""
        data = {"data": {"species": ""}}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            "geometry": "-1.286905 36.772845 0 0",
            "circumference_cm": 300,
            "meta/entity/label": "300cm purpleheart",
        }
        self.assertDictEqual(response.data, expected_data)

    def test_invalid_property(self):
        """A property that does not exist in the EntityList fails"""
        data = {"data": {"foo": "bar"}}

        self.assertTrue("foo" not in self.entity_list.properties)

        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)

    def test_anonymous_user(self):
        """Anonymous user cannot update Entity"""
        # Anonymous user cannot update private EntityList
        request = self.factory.patch("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)
        # Anonymous user cannot update public EntityList
        self.project.shared = True
        self.project.save()
        request = self.factory.patch("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 401)

    def test_permission_required(self):
        """User must have the right permissions to update Entity

        User must be a project owner or, project manager, or editor
        to update Entity"""
        data = {"data": {"species": "mora"}}
        alice_data = {
            "username": "alice",
            "email": "aclie@example.com",
            "password1": "password12345",
            "password2": "password12345",
            "first_name": "Alice",
            "last_name": "Hughes",
        }
        alice_profile = self._create_user_profile(alice_data)
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        for role in ROLES:
            ShareProject(self.project, "alice", role).save()
            request = self.factory.patch("/", data=data, format="json", **extra)
            response = self.view(
                request, pk=self.entity_list.pk, entity_pk=self.entity.pk
            )

            if role not in ["owner", "manager", "editor"]:
                self.assertEqual(response.status_code, 403)

            else:
                self.assertEqual(response.status_code, 200)

    def test_deleted_entity(self):
        """Deleted Entity cannot be updated"""
        self.entity.deleted_at = timezone.now()
        self.entity.save()
        request = self.factory.patch("/", data={}, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.patch("/", data={}, format="json", **self.extra)
        response = self.view(request, pk=sys.maxsize, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)


class DeleteEntityTestCase(TestAbstractViewSet):
    """Tests for delete Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"delete": "entities"})
        # Simulate existing Entity
        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees")
        self.entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "purpleheart",
                "circumference_cm": 300,
                "meta/entity/label": "300cm purpleheart",
            },
            uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
        )

    @patch("django.utils.timezone.now")
    def test_delete(self, mock_now):
        """Delete Entity works"""
        date = datetime(2024, 6, 11, 14, 9, 0, tzinfo=timezone.utc)
        mock_now.return_value = date
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.entity.refresh_from_db()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.entity.deleted_at, date)
        self.assertEqual(self.entity.deleted_by, self.user)

    def test_invalid_entity(self):
        """Invalid Entity is handled"""
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=sys.maxsize, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_entity_already_deleted(self):
        """Deleted Entity cannot be deleted"""
        self.entity.deleted_at = timezone.now()
        self.entity.save()
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user(self):
        """Anonymous user cannot delete Entity"""
        # Anonymous user cannot delete private EntityList
        request = self.factory.delete("/")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)
        # Anonymous user cannot delete public EntityList
        self.project.shared = True
        self.project.save()
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 401)

    def test_permission_required(self):
        """User must have the right permissions to delete Entity

        User must be a project owner or, project manager, or editor
        to delete Entity"""
        alice_data = {
            "username": "alice",
            "email": "aclie@example.com",
            "password1": "password12345",
            "password2": "password12345",
            "first_name": "Alice",
            "last_name": "Hughes",
        }
        alice_profile = self._create_user_profile(alice_data)
        extra = {"HTTP_AUTHORIZATION": f"Token {alice_profile.user.auth_token}"}

        def restore_entity():
            self.entity.deleted_at = None
            self.entity.deleted_by = None
            self.entity.save()

        for role in ROLES:
            restore_entity()
            ShareProject(self.project, "alice", role).save()
            request = self.factory.delete("/", **extra)
            response = self.view(
                request, pk=self.entity_list.pk, entity_pk=self.entity.pk
            )

            if role not in ["owner", "manager", "editor"]:
                self.assertEqual(response.status_code, 403)

            else:
                self.assertEqual(response.status_code, 204)
