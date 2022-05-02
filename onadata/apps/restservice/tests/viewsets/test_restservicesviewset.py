# -*- coding: utf-8 -*-
"""
Test /restservices API endpoint implementation.
"""
from django.test.utils import override_settings

from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.viewsets.restservices_viewset import RestServicesViewSet


class TestRestServicesViewSet(TestAbstractViewSet):
    """
    Test /restservices API endpoint implementation.
    """

    def setUp(self):
        super(TestRestServicesViewSet, self).setUp()
        self.view = RestServicesViewSet.as_view(
            {
                "delete": "destroy",
                "get": "retrieve",
                "post": "create",
                "put": "update",
                "patch": "partial_update",
            }
        )
        self._publish_xls_form_to_project()

    def test_create(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "generic_json",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, RestService.objects.all().count())

    def test_textit_service_missing_params(self):
        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    def _create_textit_service(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(count + 1, RestService.objects.all().count())

        meta = MetaData.objects.filter(object_id=self.xform.id, data_type="textit")
        self.assertEqual(len(meta), 1)
        rs = RestService.objects.last()

        expected_dict = {
            "name": "textit",
            "contacts": "ksadaskjdajsda",
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "service_url": "https://textit.io",
            "id": rs.pk,
            "xform": self.xform.pk,
            "active": True,
            "inactive_reason": "",
            "flow_title": "",
        }
        response.data.pop("date_modified")
        response.data.pop("date_created")

        self.assertEqual(response.data, expected_dict)

        return response.data

    def test_create_textit_service(self):
        self._create_textit_service()

    def test_retrieve_textit_services(self):
        response_data = self._create_textit_service()

        _id = response_data.get("id")

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=_id)
        expected_dict = {
            "name": "textit",
            "contacts": "ksadaskjdajsda",
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "service_url": "https://textit.io",
            "id": _id,
            "xform": self.xform.pk,
            "active": True,
            "inactive_reason": "",
            "flow_title": "",
        }
        response.data.pop("date_modified")
        response.data.pop("date_created")

        self.assertEqual(response.data, expected_dict)

    def test_delete_textit_service(self):
        rest = self._create_textit_service()
        count = RestService.objects.all().count()
        meta_count = MetaData.objects.filter(
            object_id=self.xform.id, data_type="textit"
        ).count()

        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=rest["id"])

        self.assertEqual(response.status_code, 204)
        self.assertEqual(count - 1, RestService.objects.all().count())
        a_meta_count = MetaData.objects.filter(
            object_id=self.xform.id, data_type="textit"
        ).count()
        self.assertEqual(meta_count - 1, a_meta_count)

    def test_update(self):
        rest = RestService(
            name="testservice", service_url="http://serviec.io", xform=self.xform
        )
        rest.save()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
            "flow_title": "test-flow",
        }

        request = self.factory.put("/", data=post_data, **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "textit")
        self.assertEqual(response.data["flow_title"], "test-flow")
        metadata_count = MetaData.objects.count()

        # Flow title can be updated
        put_data = {
            "flow_title": "new-name",
            "xform": self.xform.pk,
            "name": "textit",
            "service_url": "https://textit.io",
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }
        request = self.factory.put("/", data=put_data, **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["flow_title"], "new-name")
        self.assertEqual(MetaData.objects.count(), metadata_count)

    def test_update_with_errors(self):
        rest = self._create_textit_service()

        data_value = "{}|{}".format("test", "test2")
        MetaData.textit(self.xform, data_value)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=rest.get("id"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            [
                "Error occurred when loading textit service."
                "Resolve by updating auth_token, flow_uuid and "
                "contacts fields"
            ],
        )

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }

        request = self.factory.put("/", data=post_data, **self.extra)
        response = self.view(request, pk=rest.get("id"))

        self.assertEqual(response.status_code, 200)

    def test_delete(self):
        rest = RestService(
            name="testservice", service_url="http://serviec.io", xform=self.xform
        )
        rest.save()

        count = RestService.objects.all().count()

        request = self.factory.delete("/", **self.extra)
        response = self.view(request, pk=rest.pk)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(count - 1, RestService.objects.all().count())

    def test_retrieve(self):
        rest = RestService(
            name="testservice", service_url="http://serviec.io", xform=self.xform
        )
        rest.save()

        request = self.factory.get("/", **self.extra)
        response = self.view(request, pk=rest.pk)

        data = {
            "id": rest.pk,
            "xform": self.xform.pk,
            "name": "testservice",
            "service_url": "http://serviec.io",
            "active": True,
            "inactive_reason": "",
        }
        response.data.pop("date_modified")
        response.data.pop("date_created")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data, data)

    def test_duplicate_rest_service(self):
        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 201)

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("requests.post")
    def test_textit_flow(self, mock_http):
        rest = RestService(
            name="textit", service_url="https://server.io", xform=self.xform
        )
        rest.save()

        MetaData.textit(
            self.xform,
            data_value="{}|{}|{}".format(
                "sadsdfhsdf", "sdfskhfskdjhfs", "ksadaskjdajsda"
            ),
        )

        self.assertFalse(mock_http.called)
        self._make_submissions()

        self.assertTrue(mock_http.called)
        self.assertEqual(mock_http.call_count, 4)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch("requests.post")
    def test_textit_flow_without_parsed_instances(self, mock_http):
        rest = RestService(
            name="textit", service_url="https://server.io", xform=self.xform
        )
        rest.save()

        MetaData.textit(
            self.xform,
            data_value="{}|{}|{}".format(
                "sadsdfhsdf", "sdfskhfskdjhfs", "ksadaskjdajsda"
            ),
        )
        self.assertFalse(mock_http.called)
        self._make_submissions()
        self.assertTrue(mock_http.called)

    def test_create_rest_service_invalid_form_id(self):
        count = RestService.objects.all().count()

        post_data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": "invalid",
            "auth_token": "sadsdfhsdf",
            "flow_uuid": "sdfskhfskdjhfs",
            "contacts": "ksadaskjdajsda",
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"xform": ["Invalid form id"]})
        self.assertEqual(count, RestService.objects.all().count())
