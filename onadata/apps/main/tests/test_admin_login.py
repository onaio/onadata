# -*- coding: utf-8 -*-
"""Tests for the admin login handoff to LOGIN_URL."""
from urllib.parse import parse_qs, urlparse

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase, override_settings


class AdminLoginHandoffTestCase(SimpleTestCase):
    """Admin defers to LOGIN_URL instead of serving its own login form.

    ``LoginUrlSettingTestCase`` pins what LOGIN_URL is; this pins that admin
    follows it, which is a separate mechanism: django-two-factor-auth patches
    ``AdminSite.login`` while ``TWO_FACTOR_PATCH_ADMIN`` is unset or True.
    Unpatched, admin's own form reaches a superuser session on a password
    alone whatever LOGIN_URL says.

    ``AdminSite.login`` is called directly rather than through /admin/login/:
    admin is absent from the shipped INSTALLED_APPS, and adding it via
    ``override_settings`` re-runs every ``AppConfig.ready`` — which re-applies
    this very patch, leaving a URL-level test unable to observe its absence.

    LOGIN_URL is relocated rather than left at its default, which a hardcoded
    redirect to the wizard would also satisfy.
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
