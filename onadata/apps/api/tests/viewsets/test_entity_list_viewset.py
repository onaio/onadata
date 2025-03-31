"""
Tests for module onadata.apps.api.viewsets.entity_list_viewset
"""

import json
import sys
import uuid
from datetime import datetime
from datetime import timezone as tz
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

import boto3
from moto import mock_aws

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.entity_list_viewset import EntityListViewSet
from onadata.apps.logger.models import (Entity, EntityHistory, EntityList,
                                        Project)
from onadata.libs.models.share_project import ShareProject
from onadata.libs.pagination import StandardPageNumberPagination
from onadata.libs.permissions import ROLES, OwnerRole
from onadata.libs.utils.user_auth import get_user_default_project


@override_settings(TIME_ZONE="UTC")
class CreateEntityListTestCase(TestAbstractViewSet):
    """Tests for creating an EntityList"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"post": "create"})
        self.project = get_user_default_project(self.user)
        self.data = {"name": "trees", "project": self.project.pk}

    def test_create(self):
        """EntityList is created"""
        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        entity_list = EntityList.objects.first()
        self.assertEqual(
            response.data,
            {
                "id": entity_list.pk,
                "name": "trees",
                "project": self.project.pk,
                "date_created": entity_list.date_created.isoformat().replace(
                    "+00:00", "Z"
                ),
                "date_modified": entity_list.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
            },
        )

    def test_auth_required(self):
        """Authentication is required"""
        request = self.factory.post("/", data={})
        response = self.view(request)
        self.assertEqual(response.status_code, 401)
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

    def test_name_required(self):
        """`name` field is required"""
        post_data = {"project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["name"][0]), "This field is required.")
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

    def test_project_required(self):
        """`project` field is required"""
        post_data = {"name": "trees"}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["project"][0]), "This field is required.")
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

    def test_name_valid(self):
        """`name` should be valid"""
        # name should not start with __
        post_data = {"name": "__trees", "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["name"][0]), "May not start with reserved prefix __."
        )
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

        # name should not include periods(.)
        # period start
        post_data = {"name": ".trees", "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["name"][0]), "May not include periods.")
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)
        # period middle
        post_data = {"name": "tre.es", "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["name"][0]), "May not include periods.")
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)
        # period end
        post_data = {"name": "trees.", "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["name"][0]), "May not include periods.")
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

        # name should not exceed 255 characters
        post_data = {"name": "x" * 256, "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["name"][0]),
            "Ensure this field has no more than 255 characters.",
        )
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

        post_data = {"name": "x" * 255, "project": self.project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 1)

    def test_project_valid(self):
        """`project` should be a valid project"""
        post_data = {"name": "trees", "project": sys.maxsize}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["project"][0]),
            f'Invalid pk "{sys.maxsize}" - object does not exist.',
        )
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 0)

    def test_object_permissions(self):
        """User must have object create level permissions"""
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

        # Public project, project NOT shared with user
        self.project.shared = True
        self.project.save()
        request = self.factory.post("/", data=self.data, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

        # Private project, project NOT shared with user
        self.project.shared = False
        self.project.save()
        request = self.factory.post("/", data=self.data, **extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["project"][0]),
            f'Invalid pk "{self.project.pk}" - object does not exist.',
        )

        # Project shared with user
        for role in ROLES:
            EntityList.objects.all().delete()
            ShareProject(self.project, "alice", role).save()
            request = self.factory.post("/", data=self.data, **extra)
            response = self.view(request)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 201)

            else:
                self.assertEqual(response.status_code, 403)

    def test_name_unique(self):
        """`name` should be unique per project"""
        EntityList.objects.create(name="trees", project=self.project)
        request = self.factory.post("/", data=self.data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["non_field_errors"][0]),
            "The fields name, project must make a unique set.",
        )
        project = Project.objects.create(
            name="Other project",
            created_by=self.user,
            organization=self.user,
        )
        post_data = {"name": "trees", "project": project.pk}
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        num_datasets = EntityList.objects.count()
        self.assertEqual(num_datasets, 2)


class GetEntityListArrayTestCase(TestAbstractViewSet):
    """Tests for getting an array of EntityList"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "list"})
        self._publish_registration_form(self.user)
        self._publish_follow_up_form(self.user)
        self.trees_entity_list = EntityList.objects.get(name="trees")
        OwnerRole.add(self.user, self.trees_entity_list)
        # Create more EntityLists explicitly
        self._create_entity_list("immunization")
        self._create_entity_list("savings")

    def _create_entity_list(self, name, project=None):
        if project is None:
            project = self.project

        entity_list = EntityList.objects.create(name=name, project=project)
        OwnerRole.add(self.user, entity_list)

    @override_settings(TIME_ZONE="UTC")
    def test_get_all(self):
        """Getting all EntityLists works"""
        with self.captureOnCommitCallbacks(execute=True):
            Entity.objects.create(
                entity_list=self.trees_entity_list,
                json={
                    "species": "purpleheart",
                    "geometry": "-1.286905 36.772845 0 0",
                    "circumference_cm": 300,
                    "label": "300cm purpleheart",
                },
                uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
            )
        qs = EntityList.objects.all().order_by("pk")
        first = qs[0]
        second = qs[1]
        third = qs[2]
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

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))
        self.assertEqual(response.data, expected_data)

    def test_anonymous_user(self):
        """Anonymous user can only view EntityLists under public projects"""
        public_project = Project.objects.create(
            name="public",
            shared=True,
            created_by=self.user,
            organization=self.user,
        )
        entity_list = EntityList.objects.create(
            name="public_entity_list", project=public_project
        )
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], entity_list.pk)

    def test_pagination(self):
        """Pagination works"""
        request = self.factory.get("/", data={"page": 1, "page_size": 1}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_filter_by_project(self):
        """Filtering by `project` query param works"""
        project_2 = Project.objects.create(
            name="Other project",
            created_by=self.user,
            organization=self.user,
        )
        self._create_entity_list("census", project_2)
        request = self.factory.get("/", data={"project": project_2.pk}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "census")

    def test_object_permissions(self):
        """Results limited to objects user has view level permissions"""
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
            request = self.factory.get("/", **extra)
            response = self.view(request)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 3)

            else:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 0)

    def test_soft_deleted_excluded(self):
        """Soft deleted items are excluded"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        for entity_list in EntityList.objects.all():
            entity_list.soft_delete()

        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_num_entities_cached(self):
        """`num_entities` includes cached counter"""
        entity_list = EntityList.objects.get(name="trees")
        entity_list.num_entities = 5
        entity_list.save()
        cache.set(f"elist-num-entities-{entity_list.pk}", 7)

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["num_entities"], 12)

        # Defaults to database counter if cache inaccessible
        with patch.object(cache, "get") as mock_cache_get:
            with patch("onadata.libs.utils.cache_tools.logger.exception") as mock_exc:
                mock_cache_get.side_effect = ConnectionError
                request = self.factory.get("/", **self.extra)
                response = self.view(request)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data[0]["num_entities"], 5)
                mock_exc.assert_called()


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
        OwnerRole.add(self.user, trees_entity_list)

        with self.captureOnCommitCallbacks(execute=True):
            Entity.objects.create(
                entity_list=trees_entity_list,
                json={
                    "species": "purpleheart",
                    "geometry": "-1.286905 36.772845 0 0",
                    "circumference_cm": 300,
                    "label": "300cm purpleheart",
                },
                uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
            )

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

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_object_permissions(self):
        """User must have object view level permissions"""
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
            request = self.factory.get("/", **extra)
            response = self.view(request, pk=self.entity_list.pk)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 404)

    def test_soft_deleted(self):
        """Soft deleted dataset cannot be retrieved"""
        self.entity_list.soft_delete()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)

    def test_render_csv(self):
        """Render in CSV format"""
        request = self.factory.get("/", **self.extra)
        # Using `.csv` suffix
        response = self.view(request, pk=self.entity_list.pk, format="csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get("Content-Disposition"), 'attachment; filename="trees.csv"'
        )
        self.assertEqual(response["Content-Type"], "application/csv")
        # Using `Accept` header
        request = self.factory.get("/", HTTP_ACCEPT="text/csv", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get("Content-Disposition"), 'attachment; filename="trees.csv"'
        )
        self.assertEqual(response["Content-Type"], "application/csv")


class DeleteEntityListTestCase(TestAbstractViewSet):
    """Tests for deleting a single EntityList"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"delete": "destroy"})
        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)
        OwnerRole.add(self.user, self.entity_list)

    @patch("django.utils.timezone.now")
    def test_delete(self, mock_now):
        """Delete EntityList works"""
        mocked_date = datetime(2024, 6, 25, 11, 11, 0, tzinfo=tz.utc)
        mock_now.return_value = mocked_date
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 204)
        self.entity_list.refresh_from_db()
        self.assertEqual(self.entity_list.deleted_at, mocked_date)
        self.assertEqual(self.entity_list.deleted_by, self.user)
        self.assertEqual(
            self.entity_list.name, f'trees{mocked_date.strftime("-deleted-at-%s")}'
        )

    def test_authentication_required(self):
        """Anonymous user cannot delete EntityList"""
        # Private EntityList
        request = self.factory.delete("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)
        # Public EntityList
        self.project.shared = True
        self.project.save()
        request = self.factory.delete("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_object_permissions(self):
        """User must have delete level permission"""
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

        def restore_dataset():
            self.entity_list.deleted_at = None
            self.entity_list.deleted_by = None
            self.entity_list.save()

        for role in ROLES:
            restore_dataset()
            ShareProject(self.project, "alice", role).save()
            request = self.factory.delete("/", **extra)
            response = self.view(request, pk=self.entity_list.pk)

            if role not in ["owner", "manager"]:
                self.assertEqual(response.status_code, 404)

            else:
                self.assertEqual(response.status_code, 204)

    def test_already_soft_deleted(self):
        """Soft deleted EntityList cannot be deleted"""
        deleted_at = timezone.now()
        self.entity_list.deleted_at = deleted_at
        self.entity_list.save()
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.entity_list.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.entity_list.deleted_at, deleted_at)


@override_settings(TIME_ZONE="UTC")
class GetEntitiesListTestCase(TestAbstractViewSet):
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
        OwnerRole.add(self.user, self.entity_list)
        (
            Entity.objects.create(
                entity_list=self.entity_list,
                json={
                    "geometry": "-1.286905 36.772845 0 0",
                    "species": "purpleheart",
                    "circumference_cm": 300,
                    "label": "300cm purpleheart",
                },
                uuid="dbee4c32-a922-451c-9df7-42f40bf78f48",
            ),
        )
        Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.305796 36.791849 0 0",
                "species": "wallaba",
                "circumference_cm": 100,
                "intake_notes": "Looks malnourished",
                "label": "100cm wallaba",
            },
            uuid="517185b4-bc06-450c-a6ce-44605dec5480",
        )
        entity_qs = Entity.objects.all().order_by("pk")
        pk = self.entity_list.pk
        self.expected_data = [
            {
                "url": f"http://testserver/api/v2/entity-lists/{pk}/entities/{entity_qs[0].pk}",
                "id": entity_qs[0].pk,
                "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
                "date_created": entity_qs[0]
                .date_created.isoformat()
                .replace("+00:00", "Z"),
                "data": {
                    "geometry": "-1.286905 36.772845 0 0",
                    "species": "purpleheart",
                    "circumference_cm": 300,
                    "label": "300cm purpleheart",
                },
            },
            {
                "url": f"http://testserver/api/v2/entity-lists/{pk}/entities/{entity_qs[1].pk}",
                "id": entity_qs[1].pk,
                "uuid": "517185b4-bc06-450c-a6ce-44605dec5480",
                "date_created": entity_qs[1]
                .date_created.isoformat()
                .replace("+00:00", "Z"),
                "data": {
                    "geometry": "-1.305796 36.791849 0 0",
                    "species": "wallaba",
                    "circumference_cm": 100,
                    "intake_notes": "Looks malnourished",
                    "label": "100cm wallaba",
                },
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
        # Private EntityList
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)
        # Public EntityList
        self.project.shared = True
        self.project.save()
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.expected_data)

    def test_object_permissions(self):
        """User must have EntityList view level permissions"""
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
            request = self.factory.get("/", **extra)
            response = self.view(request, pk=self.entity_list.pk)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, self.expected_data)

            else:
                self.assertEqual(response.status_code, 404)

    def test_pagination(self):
        """Pagination works"""
        request = self.factory.get("/", data={"page": 1, "page_size": 1}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["uuid"], "dbee4c32-a922-451c-9df7-42f40bf78f48"
        )
        # Unpaginated results do not exceed default page_size
        with patch.object(StandardPageNumberPagination, "page_size", 1):
            request = self.factory.get("/", **self.extra)
            response = self.view(request, pk=self.entity_list.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 1)

        # Paginated page_size should not exceed max_page_size
        with patch.object(StandardPageNumberPagination, "max_page_size", 1):
            request = self.factory.get(
                "/", data={"page": 1, "page_size": 2}, **self.extra
            )
            response = self.view(request, pk=self.entity_list.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 1)

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

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_search(self):
        """Search works"""
        # Search data json value
        request = self.factory.get("/", data={"search": "wallaba"}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Search data json key
        request = self.factory.get("/", data={"search": "intake_notes"}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Search by uuid
        request = self.factory.get(
            "/", data={"search": "dbee4c32-a922-451c-9df7-42f40bf78f48"}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Search not found
        request = self.factory.get("/", data={"search": "alkalalalkalal"}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        # Search with pagination
        request = self.factory.get(
            "/",
            data={"search": "circumference_cm", "page": 1, "page_size": 1},
            **self.extra,
        )
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


@override_settings(TIME_ZONE="UTC")
class GetSingleEntityTestCase(TestAbstractViewSet):
    """Tests for getting a single Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "entities"})
        self._create_entity()
        OwnerRole.add(self.user, self.entity_list)

    def test_get_entity(self):
        """Getting a single Entity works"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "id": self.entity.pk,
                "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
                "date_created": self.entity.date_created.isoformat().replace(
                    "+00:00", "Z"
                ),
                "date_modified": self.entity.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
                "data": {
                    "geometry": "-1.286905 36.772845 0 0",
                    "species": "purpleheart",
                    "circumference_cm": 300,
                    "label": "300cm purpleheart",
                },
            },
        )

    def test_invalid_entity(self):
        """Invalid Entity is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=sys.maxsize, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_entity_already_deleted(self):
        """Deleted Entity cannot be retrieved"""
        self.entity.deleted_at = timezone.now()
        self.entity.save()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user(self):
        """Anonymous user cannot get a private Entity"""
        # Anonymous user cannot get private Entity
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)
        # Anonymous user can get public Entity
        self.project.shared = True
        self.project.save()
        request = self.factory.get("/")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)

    def test_object_permissions(self):
        """User must have EntityList view level permissions"""
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
            request = self.factory.get("/", **extra)
            response = self.view(
                request, pk=self.entity_list.pk, entity_pk=self.entity.pk
            )

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 404)

    def test_belongs_to_dataset(self):
        """Entity belongs to the EntityList requested"""
        entity_list = EntityList.objects.create(
            name="immunization", project=self.project
        )
        entity = Entity.objects.create(
            entity_list=entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "greenheart",
                "circumference_cm": 200,
                "label": "200cm greenheart",
            },
            uuid="ff9e7dc8-7093-4269-9b6c-476a9704399b",
        )
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=entity.pk)

        self.assertEqual(response.status_code, 404)


@override_settings(TIME_ZONE="UTC")
class CreateEntityTestCase(TestAbstractViewSet):
    """Tests for creating a single Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"post": "entities"})
        self._publish_registration_form(self.user)
        self.entity_list = EntityList.objects.get(name="trees")
        OwnerRole.add(self.user, self.entity_list)
        self.data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": 30,
            },
        }

    @patch("django.utils.timezone.now")
    def test_create_entity(self, mock_now):
        """Creating single Entity works"""
        mock_date = datetime(2024, 8, 26, 14, 40, 0, tzinfo=tz.utc)
        mock_now.return_value = mock_date
        request = self.factory.post("/", data=self.data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.entity_list.refresh_from_db()
        self.assertEqual(Entity.objects.count(), 1)
        entity = Entity.objects.get(uuid="0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e")
        self.assertEqual(response.status_code, 201)
        expected_json = {
            "label": "30cm mora",
            "geometry": "-1.286805 36.772845 0 0",
            "species": "mora",
            "circumference_cm": "30",
        }
        self.assertEqual(
            response.data,
            {
                "id": entity.pk,
                "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
                "date_created": entity.date_created.isoformat().replace("+00:00", "Z"),
                "date_modified": entity.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
                "data": expected_json,
            },
        )
        self.assertEqual(entity.json, expected_json)
        self.assertEqual(self.entity_list.last_entity_update_time, mock_date)
        history = EntityHistory.objects.first()
        self.assertEqual(history.entity, entity)
        self.assertIsNone(history.registration_form)
        self.assertIsNone(history.instance)
        self.assertIsNone(history.xml)
        self.assertIsNone(history.form_version)
        self.assertDictEqual(history.json, expected_json)
        self.assertEqual(history.created_by, self.user)

    def test_label_required(self):
        """`label` field is required"""
        # Required
        data = {
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": 30,
            },
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["label"][0]), "This field is required.")
        self.assertEqual(Entity.objects.count(), 0)
        # Should not be blank
        data = {
            "label": "",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": 30,
            },
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["label"][0]), "This field may not be blank.")
        self.assertEqual(Entity.objects.count(), 0)

    def test_data_required(self):
        """`data` field is required"""
        # Missing field
        data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["data"][0]), "This field is required.")
        self.assertEqual(Entity.objects.count(), 0)
        # Empty JSON
        data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {},
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["data"][0]), "This field may not be empty.")
        self.assertEqual(Entity.objects.count(), 0)

    def test_uuid_optional(self):
        """`uuid` field is optional"""
        # UUID is generated internally
        data = {
            "label": "30cm mora",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": 30,
            },
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Entity.objects.count(), 1)
        entity = Entity.objects.first()
        self.assertIsInstance(entity.uuid, uuid.UUID)

    def test_invalid_property(self):
        """A property that does not exist in the EntityList fails"""
        data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "jane": "doe",
                "foo": "bar",
                "circumference_cm": 30,
            },
        }
        self.assertTrue("foo" not in self.entity_list.properties)

        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Invalid dataset properties: jane, foo", str(response.data["data"][0])
        )

    def test_anonymous_user(self):
        """Anonymous user cannot update Entity"""
        # Anonymous user cannot create private Entity
        request = self.factory.post("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)
        # Anonymous user cannot create public Entity
        self.project.shared = True
        self.project.save()
        request = self.factory.patch("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)

    def test_object_permissions(self):
        """User must have create level permissions"""
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
            request = self.factory.post("/", data=self.data, format="json", **extra)
            response = self.view(request, pk=self.entity_list.pk)

            if role not in ["owner", "manager"]:
                self.assertEqual(response.status_code, 404)

            else:
                self.assertEqual(response.status_code, 201)
                Entity.objects.all().delete()

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.post("/", data={}, format="json", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_empty_properties(self):
        """Empty properties are not saved"""
        data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": "",
            },
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 201)
        entity = Entity.objects.first()
        expected_json = {
            "label": "30cm mora",
            "geometry": "-1.286805 36.772845 0 0",
            "species": "mora",
        }
        self.assertEqual(
            response.data,
            {
                "id": entity.pk,
                "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
                "date_created": entity.date_created.isoformat().replace("+00:00", "Z"),
                "date_modified": entity.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
                "data": expected_json,
            },
        )
        self.assertEqual(entity.json, expected_json)

    def test_null_properties(self):
        """Null properties not allowed"""
        data = {
            "label": "30cm mora",
            "uuid": "0c5cb7fe-9f5f-4ca5-84ca-127e35a7c65e",
            "data": {
                "geometry": "-1.286805 36.772845 0 0",
                "species": "mora",
                "circumference_cm": None,
            },
        }
        request = self.factory.post("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Invalid dataset properties: circumference_cm. Nulls are not allowed",
            str(response.data["data"][0]),
        )

    def test_uuid_unique(self):
        """`uuid` is unique per Entity List"""
        Entity.objects.create(entity_list=self.entity_list, uuid=self.data["uuid"])
        request = self.factory.post("/", data=self.data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "An Entity with that uuid already exists",
            str(response.data["uuid"][0]),
        )


@override_settings(TIME_ZONE="UTC")
class UpdateEntityTestCase(TestAbstractViewSet):
    """Tests for updating a single Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view(
            {"put": "entities", "patch": "entities"},
        )
        self._create_entity()
        OwnerRole.add(self.user, self.entity_list)

    @patch("django.utils.timezone.now")
    def test_updating_entity(self, mock_now):
        """Updating an Entity works"""
        mock_date = datetime(2024, 6, 12, 12, 34, 0, tzinfo=tz.utc)
        mock_now.return_value = mock_date
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
        self.entity.refresh_from_db()
        self.entity_list.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        expected_json = {
            "geometry": "-1.286805 36.772845 0 0",
            "species": "mora",
            "circumference_cm": "30",
            "label": "30cm mora",
        }

        self.assertDictEqual(
            response.data,
            {
                "id": self.entity.pk,
                "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
                "date_created": self.entity.date_created.isoformat().replace(
                    "+00:00", "Z"
                ),
                "date_modified": self.entity.date_modified.isoformat().replace(
                    "+00:00", "Z"
                ),
                "data": expected_json,
            },
        )
        self.assertDictEqual(self.entity.json, expected_json)
        self.assertEqual(self.entity_list.last_entity_update_time, mock_date)
        self.assertEqual(EntityHistory.objects.count(), 1)
        history = EntityHistory.objects.first()
        self.assertEqual(history.entity, self.entity)
        self.assertIsNone(history.registration_form)
        self.assertIsNone(history.instance)
        self.assertIsNone(history.xml)
        self.assertIsNone(history.form_version)
        self.assertDictEqual(history.json, expected_json)
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
        self.entity.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            "uuid": str(self.entity.uuid),
            "date_created": self.entity.date_created.isoformat().replace("+00:00", "Z"),
            "date_modified": self.entity.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
            "data": {
                **self.entity.json,
                "label": "Patched label",
            },
        }
        self.assertDictEqual(response.data, expected_data)

    def test_patch_uuid(self):
        """Patch uuid works"""
        # Patch same uuid
        data = {"uuid": str(self.entity.uuid)}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 200)

        # Patch new uuid
        data = {"uuid": "64631f40-e1d6-4401-860d-18f38ec4c2c5"}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.entity.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uuid"], "64631f40-e1d6-4401-860d-18f38ec4c2c5")
        self.assertEqual(str(self.entity.uuid), "64631f40-e1d6-4401-860d-18f38ec4c2c5")

        # New uuid should be unique
        Entity.objects.create(
            entity_list=self.entity_list, uuid="edca2c69-986d-4415-b05a-96b306faeb44"
        )
        data = {"uuid": "edca2c69-986d-4415-b05a-96b306faeb44"}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "An Entity with that uuid already exists",
            str(response.data["uuid"][0]),
        )

    def test_patch_data(self):
        """Patch data only works"""
        data = {"data": {"species": "mora"}}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.entity.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            "uuid": str(self.entity.uuid),
            "date_created": self.entity.date_created.isoformat().replace("+00:00", "Z"),
            "date_modified": self.entity.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
            "data": {
                **self.entity.json,
                "species": "mora",
            },
        }
        self.assertDictEqual(response.data, expected_data)

    def test_label_empty(self):
        """Label must be a non-empty string"""
        # Empty string
        data = {"label": ""}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["label"][0]), "This field may not be blank.")
        # Null
        data = {"label": None}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["label"][0]), "This field may not be null.")

    def test_unset_property(self):
        """Unsetting a property value works"""
        data = {"data": {"species": ""}}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.entity.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        expected_data = {
            "id": self.entity.pk,
            "uuid": "dbee4c32-a922-451c-9df7-42f40bf78f48",
            "date_created": self.entity.date_created.isoformat().replace("+00:00", "Z"),
            "date_modified": self.entity.date_modified.isoformat().replace(
                "+00:00", "Z"
            ),
            "data": {
                "geometry": "-1.286905 36.772845 0 0",
                "circumference_cm": 300,
                "label": "300cm purpleheart",
            },
        }
        self.assertDictEqual(response.data, expected_data)

    def test_invalid_property(self):
        """A property that does not exist in the EntityList fails"""
        data = {"data": {"foo": "bar"}}

        self.assertTrue("foo" not in self.entity_list.properties)

        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid dataset properties: foo", str(response.data["data"][0]))

    def test_anonymous_user(self):
        """Anonymous user cannot update Entity"""
        # Anonymous user cannot update private Entity
        request = self.factory.patch("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 401)
        # Anonymous user cannot update public Entity
        self.project.shared = True
        self.project.save()
        request = self.factory.patch("/", data={}, format="json")
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 401)

    def test_object_permissions(self):
        """User must have update level permissions"""
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

            if role not in ["owner", "manager"]:
                self.assertEqual(response.status_code, 404)

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

    def test_null_properties(self):
        """Null properties not allowed"""
        data = {"data": {"species": None}}
        request = self.factory.patch("/", data=data, format="json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Invalid dataset properties: species. Nulls are not allowed",
            str(response.data["data"][0]),
        )


class DeleteEntityTestCase(TestAbstractViewSet):
    """Tests for delete Entity"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"delete": "entities"})

        with self.captureOnCommitCallbacks(execute=True):
            self._create_entity()

        OwnerRole.add(self.user, self.entity_list)

    @patch("django.utils.timezone.now")
    def test_delete(self, mock_now):
        """Delete Entity works"""
        self.entity_list.refresh_from_db()
        self.assertEqual(cache.get(f"elist-num-entities-{self.entity_list.pk}"), 1)
        date = datetime(2024, 6, 11, 14, 9, 0, tzinfo=tz.utc)
        mock_now.return_value = date

        with self.captureOnCommitCallbacks(execute=True):
            request = self.factory.delete(
                "/", data={"entity_ids": [self.entity.pk]}, **self.extra
            )
            response = self.view(request, pk=self.entity_list.pk)
            self.entity.refresh_from_db()
            self.entity_list.refresh_from_db()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.entity.deleted_at, date)
        self.assertEqual(self.entity.deleted_by, self.user)
        self.assertEqual(cache.get(f"elist-num-entities-{self.entity_list.pk}"), 0)
        self.assertEqual(
            self.entity_list.last_entity_update_time, self.entity.date_modified
        )

    def test_entity_ids_required(self):
        """Field `entity_ids` is required"""
        request = self.factory.delete("/", data={}, **self.extra)
        response = self.view(request, pk=self.entity_list.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["entity_ids"][0]), "This field is required.")

    def test_invalid_entity(self):
        """Invalid Entity is handled"""
        request = self.factory.delete(
            "/", data={"entity_ids": [sys.maxsize]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["entity_ids"][0]), "One or more entities does not exist."
        )

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=sys.maxsize, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 404)

    def test_entity_already_deleted(self):
        """Deleted Entity cannot be deleted"""
        self.entity.deleted_at = timezone.now()
        self.entity.save()
        request = self.factory.delete(
            "/", data={"entity_ids": [self.entity.pk]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["entity_ids"][0]), "One or more entities does not exist."
        )

    def test_anonymous_user(self):
        """Anonymous user cannot delete Entity"""
        # Anonymous user cannot delete private Entity
        request = self.factory.delete("/")
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)
        # Anonymous user cannot delete public Entity
        self.project.shared = True
        self.project.save()
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 401)

    def test_object_permissions(self):
        """User must have delete level permissions"""
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
            request = self.factory.delete(
                "/", data={"entity_ids": [self.entity.pk]}, **extra
            )
            response = self.view(request, pk=self.entity_list.pk)

            if role not in ["owner", "manager"]:
                self.assertEqual(response.status_code, 404)

            else:
                self.assertEqual(response.status_code, 204)

    @patch("django.utils.timezone.now")
    def test_delete_bulk(self, mock_now):
        """Deleting Entities in bulk works"""
        date = datetime(2024, 6, 11, 14, 9, 0, tzinfo=tz.utc)
        mock_now.return_value = date
        entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "greenheart",
                "circumference_cm": 200,
                "label": "200cm greenheart",
            },
            uuid="ff9e7dc8-7093-4269-9b6c-476a9704399b",
        )
        request = self.factory.delete(
            "/", data={"entity_ids": [self.entity.pk, entity.pk]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)
        self.entity_list.refresh_from_db()
        self.entity.refresh_from_db()
        entity.refresh_from_db()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.entity.deleted_at, date)
        self.assertEqual(self.entity.deleted_by, self.user)
        self.assertEqual(entity.deleted_at, date)
        self.assertEqual(entity.deleted_by, self.user)
        self.assertEqual(self.entity_list.num_entities, 0)
        self.assertEqual(self.entity_list.last_entity_update_time, entity.date_modified)

    def test_delete_bulk_invalid_id(self):
        """Invalid Entities when deleting in bulk handled"""
        request = self.factory.delete(
            "/", data={"entity_ids": [self.entity.pk, sys.maxsize]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["entity_ids"][0]), "One or more entities does not exist."
        )

    @patch(
        "onadata.libs.serializers.entity_serializer.delete_entities_bulk_async.delay"
    )
    def test_bulk_delete_async(self, mock_delete):
        """Deleting Entities in bulk should be asynchronous"""
        entity = Entity.objects.create(
            entity_list=self.entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "greenheart",
                "circumference_cm": 200,
                "label": "200cm greenheart",
            },
            uuid="ff9e7dc8-7093-4269-9b6c-476a9704399b",
        )
        request = self.factory.delete(
            "/", data={"entity_ids": [self.entity.pk, entity.pk]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 204)
        mock_delete.assert_called_once_with(
            [self.entity.pk, entity.pk], self.user.username
        )

    def test_belongs_to_dataset(self):
        """The Entities being deleted belong to the EntityList"""
        entity_list = EntityList.objects.create(
            name="immunization", project=self.project
        )
        entity = Entity.objects.create(
            entity_list=entity_list,
            json={
                "geometry": "-1.286905 36.772845 0 0",
                "species": "greenheart",
                "circumference_cm": 200,
                "label": "200cm greenheart",
            },
            uuid="ff9e7dc8-7093-4269-9b6c-476a9704399b",
        )
        request = self.factory.delete(
            "/", data={"entity_ids": [entity.pk]}, **self.extra
        )
        response = self.view(request, pk=self.entity_list.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["entity_ids"][0]), "One or more entities does not exist."
        )

    def test_delete_via_kwarg_invalid(self):
        """ID to be deleted is specified only via payload"""
        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, entity_pk=self.entity.pk)
        self.assertEqual(response.status_code, 405)


class DownloadEntityListTestCase(TestAbstractViewSet):
    """Tests for `download` action"""

    def setUp(self):
        super().setUp()

        self.view = EntityListViewSet.as_view({"get": "download"})
        self.project = get_user_default_project(self.user)
        self.entity_list = EntityList.objects.create(name="trees", project=self.project)
        OwnerRole.add(self.user, self.entity_list)

    def test_download(self):
        """EntityList dataset is downloaded"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="trees.csv"'
        )
        self.assertEqual(response["Content-Type"], "application/csv")
        # Using `.csv` suffix
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, format="csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="trees.csv"'
        )
        self.assertEqual(response["Content-Type"], "application/csv")
        # Using `Accept` header
        request = self.factory.get("/", HTTP_ACCEPT="text/csv", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get("Content-Disposition"), 'attachment; filename="trees.csv"'
        )
        self.assertEqual(response["Content-Type"], "application/csv")
        # Unsupported suffix
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk, format="json")
        self.assertEqual(response.status_code, 404)
        # Unsupported accept header
        request = self.factory.get("/", HTTP_ACCEPT="application/json", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user(self):
        """Anonymous user cannot download a private EntityList"""
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

    def test_invalid_entity_list(self):
        """Invalid EntityList is handled"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=sys.maxsize)
        self.assertEqual(response.status_code, 404)

    def test_object_permissions(self):
        """User must have object view level permissions"""
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
            request = self.factory.get("/", **extra)
            response = self.view(request, pk=self.entity_list.pk)

            if role in ["owner", "manager"]:
                self.assertEqual(response.status_code, 200)

            else:
                self.assertEqual(response.status_code, 404)

    def test_soft_deleted(self):
        """Soft deleted dataset cannot be retrieved"""
        self.entity_list.soft_delete()
        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=self.entity_list.pk)
        self.assertEqual(response.status_code, 404)

    def test_download_from_s3(self):
        """EntityList dataset is downloaded from Amazon S3"""
        request = self.factory.get("/", **self.extra)
        with override_settings(
            STORAGES={"default": {"BACKEND": "storages.backends.s3.S3Storage"}},
            AWS_STORAGE_BUCKET_NAME="testing",
        ):
            with mock_aws():
                s3 = boto3.resource("s3", region_name='us-east-1')
                bucket = s3.Bucket('testing')
                bucket.create()
                response = self.view(request, pk=self.entity_list.pk)
                self.assertEqual(response.status_code, 302)
                self.assertIn("response-content-disposition", response.url)
