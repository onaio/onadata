# -*- coding: utf-8 -*-
"""Tests for URL configuration when django.contrib.admin toggles in INSTALLED_APPS."""
import importlib

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, resolve, reverse

from onadata.apps.api.urls import v1_urls as api_v1_urls_module
from onadata.apps.main import urls as main_urls_module


class TestUrlsAdminToggle(SimpleTestCase):

    """Verify the admin conditional in main/urls.py actually toggles."""

    def tearDown(self):
        """Reload URL modules so later tests see the real settings URLconf."""
        clear_url_caches()
        importlib.reload(main_urls_module)
        importlib.reload(api_v1_urls_module)

    def _adminless_installed_apps(self):
        return [
            app
            for app in settings.INSTALLED_APPS
            if app not in ("django.contrib.admin", "django.contrib.admindocs")
        ]

    def _adminful_installed_apps(self):
        apps = list(settings.INSTALLED_APPS)
        for app in ("django.contrib.admin", "django.contrib.admindocs"):
            if app not in apps:
                apps.append(app)
        return apps

    def _reload_urlconfs(self):
        clear_url_caches()
        importlib.reload(main_urls_module)
        importlib.reload(api_v1_urls_module)

    def test_main_urls_reload_without_admin(self):
        """main/urls.py re-executes cleanly when admin is absent."""
        with override_settings(INSTALLED_APPS=self._adminless_installed_apps()):
            self._reload_urlconfs()
            self.assertIsNotNone(main_urls_module.urlpatterns)

    def test_v1_urls_reload_without_admin(self):
        """api/urls/v1_urls.py re-executes cleanly when admin is absent."""
        with override_settings(INSTALLED_APPS=self._adminless_installed_apps()):
            self._reload_urlconfs()
            self.assertIsNotNone(api_v1_urls_module.router)

    def test_api_v1_route_resolves_without_admin(self):
        """/api/v1/ resolves when admin is absent."""
        with override_settings(INSTALLED_APPS=self._adminless_installed_apps()):
            self._reload_urlconfs()
            resolved = resolve("/api/v1/")
            self.assertEqual(resolved.url_name, "api-root")

    def test_api_v2_route_resolves_without_admin(self):
        """/api/v2/ resolves when admin is absent."""
        with override_settings(INSTALLED_APPS=self._adminless_installed_apps()):
            self._reload_urlconfs()
            resolved = resolve("/api/v2/")
            self.assertEqual(resolved.url_name, "api-root")

    def test_admin_namespace_absent_without_admin(self):
        """admin: URL namespace is not registered when admin is absent."""
        with override_settings(INSTALLED_APPS=self._adminless_installed_apps()):
            self._reload_urlconfs()
            with self.assertRaises(NoReverseMatch):
                reverse("admin:index")

    def test_admin_namespace_present_with_admin(self):
        """admin: URL namespace is registered when admin is in INSTALLED_APPS."""
        with override_settings(INSTALLED_APPS=self._adminful_installed_apps()):
            self._reload_urlconfs()
            # Should not raise.
            reverse("admin:index")
