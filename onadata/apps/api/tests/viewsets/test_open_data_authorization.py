"""Authorization and capability-disclosure tests for OpenData endpoints."""

import json
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.utils import timezone

from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.v2.tableau_viewset import TableauViewSet
from onadata.apps.logger.models import OpenData, Project, XForm
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ManagerRole
from onadata.libs.utils.user_auth import get_user_default_project


class TestOpenDataAuthorization(TestBase):
    """OpenData management must follow XForm change permissions."""

    viewset_classes = (OpenDataViewSet, TableauViewSet)

    def setUp(self):
        super().setUp()
        self._publish_transportation_form()
        self.owner_xform = self.xform
        self.owner_open_data = get_or_create_opendata(self.owner_xform)[0]
        self.owner_auth = {
            "HTTP_AUTHORIZATION": f"Token {self.user.auth_token}",
        }

        self.other_user = self._create_user("alice", "alice", create_profile=True)
        other_project = get_user_default_project(self.other_user)
        self.other_xform = XForm.objects.create(
            xml=self.owner_xform.xml,
            json=self.owner_xform.json,
            user=self.other_user,
            created_by=self.other_user,
            project=other_project,
        )
        ManagerRole.add(self.other_user, self.other_xform)
        self.other_open_data = get_or_create_opendata(self.other_xform)[0]
        self.other_auth = {
            "HTTP_AUTHORIZATION": f"Token {self.other_user.auth_token}",
        }
        self.factory = RequestFactory()

    def _create_data(self, xform=None):
        xform = xform or self.owner_xform
        return {
            "object_id": xform.id,
            "data_type": "xform",
            "name": xform.id_string,
        }

    @staticmethod
    def _list_results(response):
        if isinstance(response.data, dict):
            return response.data.get("results", response.data)

        return response.data

    def test_unrelated_user_cannot_create_or_discover_existing_capability(self):
        """Authorization happens before any OpenData row lookup or creation."""
        initial_count = OpenData.objects.count()
        for viewset_class in self.viewset_classes:
            with self.subTest(viewset=viewset_class.__name__):
                view = viewset_class.as_view({"post": "create"})
                request = self.factory.post(
                    "/", data=self._create_data(self.other_xform), **self.owner_auth
                )

                with patch(
                    "onadata.libs.serializers.open_data_serializer."
                    "OpenData.objects.get_or_create"
                ) as get_or_create:
                    response = view(request)

                self.assertEqual(response.status_code, 404)
                get_or_create.assert_not_called()
                self.assertNotIn(self.other_open_data.uuid, json.dumps(response.data))

        self.assertEqual(OpenData.objects.count(), initial_count)

    def test_authorized_creator_receives_uuid_with_implicit_and_legacy_type(self):
        for viewset_class in self.viewset_classes:
            for data_type in (None, "xform"):
                with self.subTest(viewset=viewset_class.__name__, data_type=data_type):
                    data = self._create_data()
                    if data_type is None:
                        data.pop("data_type")

                    view = viewset_class.as_view({"post": "create"})
                    request = self.factory.post("/", data=data, **self.owner_auth)
                    response = view(request)

                    self.assertEqual(response.status_code, 201)
                    self.assertEqual(response.data["uuid"], self.owner_open_data.uuid)

    def test_create_uses_content_type_and_object_id(self):
        """An unrelated generic relation row cannot collide with an XForm."""
        self.owner_open_data.delete()
        other_content_type = ContentType.objects.get_for_model(Project)
        collision = OpenData.objects.create(
            name="not an xform",
            content_type=other_content_type,
            object_id=self.owner_xform.id,
        )
        view = OpenDataViewSet.as_view({"post": "create"})
        request = self.factory.post("/", data=self._create_data(), **self.owner_auth)

        response = view(request)

        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data["uuid"], collision.uuid)
        self.assertTrue(
            OpenData.objects.filter(
                content_type=ContentType.objects.get_for_model(XForm),
                object_id=self.owner_xform.id,
            ).exists()
        )

    def test_create_rejects_unsupported_data_type(self):
        data = self._create_data()
        data["data_type"] = "project"
        for viewset_class in self.viewset_classes:
            with self.subTest(viewset=viewset_class.__name__):
                view = viewset_class.as_view({"post": "create"})
                request = self.factory.post("/", data=data, **self.owner_auth)
                response = view(request)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.data["data_type"], ["Only xform data is supported."]
                )

    def test_create_rejects_deleted_xform(self):
        self.owner_xform.deleted_at = timezone.now()
        self.owner_xform.save(update_fields=["deleted_at"])
        view = OpenDataViewSet.as_view({"post": "create"})
        request = self.factory.post("/", data=self._create_data(), **self.owner_auth)

        response = view(request)

        self.assertEqual(response.status_code, 404)

    def test_create_rejects_xform_in_inactive_organization(self):
        organization = self._create_user("inactive-org", "")
        organization.is_active = False
        organization.save(update_fields=["is_active"])
        self.owner_xform.project.organization = organization
        self.owner_xform.project.save(update_fields=["organization"])
        view = OpenDataViewSet.as_view({"post": "create"})
        request = self.factory.post("/", data=self._create_data(), **self.owner_auth)

        response = view(request)

        self.assertEqual(response.status_code, 404)

    def test_v1_and_v2_lists_are_scoped_and_omit_uuids(self):
        for viewset_class in self.viewset_classes:
            for auth, expected_xform in (
                (self.owner_auth, self.owner_xform),
                (self.other_auth, self.other_xform),
            ):
                with self.subTest(
                    viewset=viewset_class.__name__, xform=expected_xform.id
                ):
                    view = viewset_class.as_view({"get": "list"})
                    request = self.factory.get("/", **auth)
                    response = view(request)
                    results = self._list_results(response)

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        [item["object_id"] for item in results],
                        [expected_xform.id],
                    )
                    self.assertNotIn(
                        self.owner_open_data.uuid, json.dumps(response.data)
                    )
                    self.assertNotIn(
                        self.other_open_data.uuid, json.dumps(response.data)
                    )

    def test_owner_retrieve_and_update_succeed_without_uuid_disclosure(self):
        for viewset_class in self.viewset_classes:
            with self.subTest(viewset=viewset_class.__name__):
                retrieve = viewset_class.as_view({"get": "retrieve"})
                request = self.factory.get("/", **self.owner_auth)
                response = retrieve(request, uuid=self.owner_open_data.uuid)

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("uuid", response.data)

                update = viewset_class.as_view({"patch": "partial_update"})
                request = self.factory.patch(
                    "/",
                    data=json.dumps({"name": "authorized update"}),
                    content_type="application/json",
                    **self.owner_auth,
                )
                response = update(request, uuid=self.owner_open_data.uuid)

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("uuid", response.data)

    def test_owner_destroy_succeeds_in_v1_and_v2(self):
        for viewset_class in self.viewset_classes:
            with self.subTest(viewset=viewset_class.__name__):
                open_data = get_or_create_opendata(self.owner_xform)[0]
                view = viewset_class.as_view({"delete": "destroy"})
                request = self.factory.delete("/", **self.owner_auth)

                response = view(request, uuid=open_data.uuid)

                self.assertEqual(response.status_code, 204)
                self.assertFalse(OpenData.objects.filter(pk=open_data.pk).exists())

    def test_cross_tenant_detail_management_returns_404(self):
        mappings = (
            ({"get": "retrieve"}, "get", None),
            ({"patch": "partial_update"}, "patch", {"name": "blocked"}),
            ({"delete": "destroy"}, "delete", None),
        )
        for viewset_class in self.viewset_classes:
            for mapping, method, data in mappings:
                with self.subTest(
                    viewset=viewset_class.__name__, action=next(iter(mapping.values()))
                ):
                    view = viewset_class.as_view(mapping)
                    request_method = getattr(self.factory, method)
                    if method == "patch":
                        request = request_method(
                            "/",
                            data=json.dumps(data),
                            content_type="application/json",
                            **self.owner_auth,
                        )
                    else:
                        request = request_method("/", **self.owner_auth)
                    response = view(request, uuid=self.other_open_data.uuid)

                    self.assertEqual(response.status_code, 404)

    def test_target_changing_update_requires_permission_on_new_xform(self):
        for viewset_class in self.viewset_classes:
            for object_id in (self.other_xform.id, 999999999):
                with self.subTest(viewset=viewset_class.__name__, object_id=object_id):
                    view = viewset_class.as_view({"patch": "partial_update"})
                    request = self.factory.patch(
                        "/",
                        data=json.dumps({"object_id": object_id}),
                        content_type="application/json",
                        **self.owner_auth,
                    )

                    response = view(request, uuid=self.owner_open_data.uuid)

                    self.assertEqual(response.status_code, 404)
                    self.owner_open_data.refresh_from_db()
                    self.assertEqual(
                        self.owner_open_data.object_id, self.owner_xform.id
                    )

    def test_owner_can_retrieve_uuid_but_unrelated_user_gets_404(self):
        for viewset_class in self.viewset_classes:
            for data_type in (None, "xform"):
                with self.subTest(viewset=viewset_class.__name__, data_type=data_type):
                    view = viewset_class.as_view({"get": "uuid"})
                    data = {"object_id": self.owner_xform.id}
                    if data_type is not None:
                        data["data_type"] = data_type

                    owner_request = self.factory.get("/", data=data, **self.owner_auth)
                    response = view(owner_request)

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, {"uuid": self.owner_open_data.uuid})

                    other_request = self.factory.get("/", data=data, **self.other_auth)
                    response = view(other_request)
                    self.assertEqual(response.status_code, 404)

    def test_uuid_rejects_unsupported_data_type(self):
        data = {
            "data_type": "project",
            "object_id": self.owner_xform.id,
        }
        for viewset_class in self.viewset_classes:
            with self.subTest(viewset=viewset_class.__name__):
                view = viewset_class.as_view({"get": "uuid"})
                request = self.factory.get("/", data=data, **self.owner_auth)

                response = view(request)

                self.assertEqual(response.status_code, 404)

    def test_anonymous_management_is_denied_in_v1_and_v2(self):
        initial_count = OpenData.objects.count()
        for viewset_class in self.viewset_classes:
            for mapping, method, data in (
                ({"get": "list"}, "get", None),
                ({"post": "create"}, "post", self._create_data()),
            ):
                with self.subTest(
                    viewset=viewset_class.__name__, action=next(iter(mapping.values()))
                ):
                    view = viewset_class.as_view(mapping)
                    request = getattr(self.factory, method)("/", data=data or {})
                    response = view(request)

                    self.assertEqual(response.status_code, 401)

        self.assertEqual(OpenData.objects.count(), initial_count)

    def test_anonymous_schema_and_data_remain_available_with_valid_uuid(self):
        for viewset_class in self.viewset_classes:
            for action in ("schema", "data"):
                with self.subTest(viewset=viewset_class.__name__, action=action):
                    view = viewset_class.as_view({"get": action})
                    request = self.factory.get("/")

                    response = view(request, uuid=self.owner_open_data.uuid)

                    self.assertEqual(response.status_code, 200)
