"""Tests for requests whose Host header is not a valid hostname."""

from django.test import SimpleTestCase, override_settings


@override_settings(CSRF_USE_SESSIONS=True)
class MalformedHostTestCase(SimpleTestCase):
    """A malformed Host header gets a 400, not a server error."""

    def test_malformed_host_gets_a_bad_request_response(self):
        response = self.client.get("/", HTTP_HOST="/efx")

        self.assertEqual(response.status_code, 400)
