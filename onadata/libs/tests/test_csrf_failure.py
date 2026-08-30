"""Tests for the graceful CSRF-failure handler."""
from django.test import RequestFactory, TestCase

from onadata.libs.csrf_failure import csrf_failure


class CsrfFailureTests(TestCase):
    """The login flow should self-heal on a CSRF failure; other paths default."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_login_csrf_failure_redirects_to_fresh_login(self):
        request = self.factory.post(
            "/accounts/login/", {"next": "/o/authorize/?client_id=x"}
        )
        response = csrf_failure(request, reason="CSRF token incorrect")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))
        self.assertIn("next=", response["Location"])

    def test_login_csrf_failure_without_next_redirects_to_bare_login(self):
        request = self.factory.post("/accounts/login/", {})
        response = csrf_failure(request, reason="CSRF token incorrect")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/accounts/login/")

    def test_login_csrf_failure_drops_unsafe_next(self):
        request = self.factory.post(
            "/accounts/login/", {"next": "https://evil.example.com/steal"}
        )
        response = csrf_failure(request, reason="CSRF token incorrect")
        self.assertEqual(response.status_code, 302)
        # Open-redirect target must be dropped, not preserved.
        self.assertEqual(response["Location"], "/accounts/login/")

    def test_non_login_csrf_failure_uses_default(self):
        request = self.factory.post("/api/v1/forms.json", {})
        response = csrf_failure(request, reason="CSRF token incorrect")
        # Default Django behavior: a 403, not a redirect.
        self.assertEqual(response.status_code, 403)
