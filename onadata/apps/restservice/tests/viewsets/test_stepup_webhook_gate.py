# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on creating or redirecting a REST service.
"""

from django.test.utils import override_settings
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.views import add_service
from onadata.apps.restservice.viewsets.restservices_viewset import RestServicesViewSet

CHANGE_WEBHOOK = "change-webhook"
SERVICE_URL = "https://example.com/hook"
OTHER_URL = "https://elsewhere.example.org/hook"


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [CHANGE_WEBHOOK],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestChangeWebhookGate(TestAbstractViewSet):
    """A webhook copies every submission to its URL, so a stolen session
    alone must not be able to add one or point one somewhere else."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self.view = RestServicesViewSet.as_view(
            {
                "post": "create",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        )
        self._publish_xls_form_to_project()

    def _request(self, method, data=None, headers=None, **kwargs):
        request = getattr(self.factory, method)(
            "/", data=data, format="json", **{**self.extra, **(headers or {})}
        )
        return self.view(request, **kwargs)

    def _grant_header(self):
        return {"HTTP_X_STEP_UP_GRANT": issue_grant(self.user.pk, CHANGE_WEBHOOK)}

    def _new_service(self, **overrides):
        return {
            "name": "generic_json",
            "service_url": SERVICE_URL,
            "xform": self.xform.pk,
            **overrides,
        }

    def _service(self):
        return RestService.objects.create(
            xform=self.xform, name="generic_json", service_url=SERVICE_URL
        )

    def test_creating_a_webhook_without_a_grant_is_challenged(self):
        self.assertFalse(RestService.objects.exists())

        response = self._request("post", self._new_service())

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_WEBHOOK)
        self.assertFalse(RestService.objects.exists())

    def test_a_grant_lets_the_webhook_be_created(self):
        response = self._request("post", self._new_service(), self._grant_header())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            list(RestService.objects.values_list("service_url", flat=True)),
            [SERVICE_URL],
        )

    def test_an_invalid_webhook_keeps_the_grant(self):
        """Validation comes first, so a mistyped URL does not spend it."""
        grant = issue_grant(self.user.pk, CHANGE_WEBHOOK)

        response = self._request(
            "post",
            self._new_service(service_url="not a url"),
            {"HTTP_X_STEP_UP_GRANT": grant},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("service_url", response.data)
        self.assertFalse(RestService.objects.exists())
        self.assertTrue(spend_grant(self.user.pk, CHANGE_WEBHOOK, grant))

    def test_changing_the_url_without_a_grant_is_challenged(self):
        service = self._service()

        response = self._request("patch", {"service_url": OTHER_URL}, pk=service.pk)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_WEBHOOK)
        service.refresh_from_db()
        self.assertEqual(service.service_url, SERVICE_URL)

    def test_changing_the_service_type_without_a_grant_is_challenged(self):
        service = self._service()

        response = self._request("patch", {"name": "generic_xml"}, pk=service.pk)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_WEBHOOK)
        service.refresh_from_db()
        self.assertEqual(service.name, "generic_json")

    def test_a_put_changing_the_url_without_a_grant_is_challenged(self):
        service = self._service()

        response = self._request(
            "put", self._new_service(service_url=OTHER_URL), pk=service.pk
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_WEBHOOK)
        service.refresh_from_db()
        self.assertEqual(service.service_url, SERVICE_URL)

    def test_a_grant_lets_the_url_change_through(self):
        service = self._service()

        response = self._request(
            "patch", {"service_url": OTHER_URL}, self._grant_header(), pk=service.pk
        )

        self.assertEqual(response.status_code, 200)
        service.refresh_from_db()
        self.assertEqual(service.service_url, OTHER_URL)

    def test_an_invalid_url_change_keeps_the_grant(self):
        service = self._service()
        grant = issue_grant(self.user.pk, CHANGE_WEBHOOK)

        response = self._request(
            "patch",
            {"service_url": "not a url"},
            {"HTTP_X_STEP_UP_GRANT": grant},
            pk=service.pk,
        )

        self.assertEqual(response.status_code, 400)
        service.refresh_from_db()
        self.assertEqual(service.service_url, SERVICE_URL)
        self.assertTrue(spend_grant(self.user.pk, CHANGE_WEBHOOK, grant))

    def test_a_put_echoing_the_destination_is_not_challenged(self):
        """A client saving the whole record sends the URL back unchanged."""
        service = self._service()
        self.assertTrue(service.active)

        response = self._request("put", self._new_service(active=False), pk=service.pk)

        self.assertEqual(response.status_code, 200)
        service.refresh_from_db()
        self.assertFalse(service.active)
        self.assertEqual(service.service_url, SERVICE_URL)

    def test_deleting_a_webhook_is_not_challenged(self):
        """Removing one stops data leaving, so it needs no further proof."""
        service = self._service()

        response = self._request("delete", pk=service.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(RestService.objects.filter(pk=service.pk).exists())

    def _textit_service(self):
        """A TextIt service sends to credentials kept in MetaData, not to
        ``service_url``."""
        data = {
            "name": "textit",
            "service_url": "https://textit.io",
            "xform": self.xform.pk,
            "auth_token": "token-A",
            "flow_uuid": "flow-A",
            "contacts": "contacts-A",
        }
        response = self._request("post", data, self._grant_header())
        self.assertEqual(response.status_code, 201)
        return RestService.objects.get(name="textit", xform=self.xform)

    def test_repointing_textit_credentials_without_a_grant_is_challenged(self):
        service = self._textit_service()

        response = self._request(
            "patch", {"name": "textit", "auth_token": "attacker-token"}, pk=service.pk
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], CHANGE_WEBHOOK)

    def test_a_grant_lets_textit_credentials_change(self):
        service = self._textit_service()

        response = self._request(
            "patch",
            {"name": "textit", "auth_token": "new-token"},
            self._grant_header(),
            pk=service.pk,
        )

        self.assertEqual(response.status_code, 200)


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [CHANGE_WEBHOOK],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestAddServicePageGate(TestAbstractViewSet):
    """The server-rendered page adds a webhook too, so it must not be a way
    around the API's gate."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._publish_xls_form_to_project()
        self.url = reverse(
            add_service,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )

    def _post(self, data=None):
        return self.client.post(
            self.url,
            {
                "service_name": "generic_json",
                "service_url": SERVICE_URL,
                **(data or {}),
            },
        )

    def test_adding_a_service_without_a_grant_is_refused(self):
        self.assertFalse(RestService.objects.exists())

        response = self._post()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(RestService.objects.exists())

    def test_a_grant_lets_the_service_be_added(self):
        grant = issue_grant(self.user.pk, CHANGE_WEBHOOK)

        response = self._post({"grant": grant})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(RestService.objects.values_list("service_url", flat=True)),
            [SERVICE_URL],
        )

    def test_an_invalid_service_keeps_the_grant(self):
        grant = issue_grant(self.user.pk, CHANGE_WEBHOOK)

        response = self._post({"service_url": "not a url", "grant": grant})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RestService.objects.exists())
        self.assertTrue(spend_grant(self.user.pk, CHANGE_WEBHOOK, grant))
