# -*- coding: utf-8 -*-
"""Tests for the admin login handoff to LOGIN_URL."""
from urllib.parse import parse_qs, urlparse

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase, override_settings


class AdminLoginHandoffTestCase(SimpleTestCase):
    """Admin defers to LOGIN_URL instead of serving its own login form.

    Unpatched, admin's own form reaches a superuser session on a password
    alone, whatever LOGIN_URL says.

    Called directly rather than through /admin/login/: adding admin to
    INSTALLED_APPS re-runs every ``AppConfig.ready``, which re-applies the
    very patch under test, so a URL-level test cannot observe its absence.
    LOGIN_URL is relocated because the default would also satisfy a hardcoded
    redirect.
    """

    @override_settings(LOGIN_URL="/oidc/example/login")
    def test_admin_login_defers_to_login_url(self):
        """Relocating LOGIN_URL moves the admin door with it, ?next= intact."""
        request = RequestFactory().get("/admin/login/", {"next": "/admin/"})

        response = AdminSite().login(request)

        self.assertEqual(
            response.status_code,
            302,
            "admin served its own login response instead of deferring",
        )
        location = urlparse(response["Location"])
        self.assertEqual(location.path, "/oidc/example/login")
        self.assertEqual(parse_qs(location.query)["next"], ["/admin/"])
