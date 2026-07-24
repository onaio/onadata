# -*- coding: utf-8 -*-
"""Tests for URL configuration when django.contrib.admin toggles in INSTALLED_APPS."""
import importlib

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import (
    NoReverseMatch,
    Resolver404,
    clear_url_caches,
    resolve,
    reverse,
)

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


class TestHyphenatedUsernameUrls(SimpleTestCase):
    """Username-scoped URLs must reverse for usernames containing a hyphen."""

    def test_download_xform_reverse_with_hyphenated_username(self):
        """download_xform reverses for a hyphenated username (id_string and pk)."""
        url = reverse(
            "download_xform",
            kwargs={"username": "alpha-project", "id_string": "myform"},
        )
        self.assertIn("alpha-project", url)

        url_pk = reverse(
            "download_xform",
            kwargs={"username": "alpha-project", "pk": 885480},
        )
        self.assertIn("alpha-project", url_pk)

    def test_username_scoped_urls_reverse_with_hyphenated_username(self):
        """A representative set of username-scoped URLs reverse with a hyphen."""
        username = "alpha-project"
        cases = [
            ("form-list", {"username": username}),
            ("submissions", {"username": username}),
            ("download_xlsform", {"username": username, "id_string": "myform"}),
            ("download_jsonform", {"username": username, "id_string": "myform"}),
            ("enter_data", {"username": username, "id_string": "myform"}),
            ("data-view", {"username": username, "id_string": "myform"}),
            ("manifest-url", {"username": username, "pk": 885480}),
            (
                "export-download",
                {
                    "username": username,
                    "id_string": "myform",
                    "export_type": "csv",
                    "filename": "data.csv",
                },
            ),
        ]
        for name, kwargs in cases:
            with self.subTest(url=name):
                self.assertIn(username, reverse(name, kwargs=kwargs))

    def test_metacharacter_username_does_not_match_routes(self):
        """Usernames with HTML metacharacters do not match username routes.

        The username group uses USERNAME_LOOKUP_REGEX (not the looser
        ``[^/]+``), so characters such as ``<>"'`` that cannot appear in a
        valid username never reach the underlying views.
        """
        for path in ("/<script>/formList", "/a\"b/submission", "/a'b/formUpload"):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)


class TestOidcAccountProxyUrls(SimpleTestCase):
    """The inline ``oidc`` URLconf also routes the account-proxy actions.

    These live alongside login/callback/logout/session on the same
    org-account-rejecting viewset (instead of a blanket
    ``include("oidc.urls")``), so this pins both that every account-proxy
    route resolves to the expected action and that anchoring the
    ``session`` route with ``$`` keeps it from prefix-matching ``sessions``.
    Pure URLconf resolution -- no database required.

    Assertions check individual ``method -> action`` pairs rather than the
    whole ``actions`` dict: DRF's ``ViewSetMixin.as_view()`` lazily mutates
    that (shared, process-lifetime) dict to alias ``head`` to ``get`` the
    first time the view actually dispatches a request, so its exact
    contents can vary depending on what other tests ran earlier.
    """

    def test_credentials_resolves_to_credentials_list(self):
        match = resolve("/oidc/example/credentials")
        self.assertEqual(match.func.actions.get("get"), "credentials_list")

    def test_sessions_resolves_to_sessions_list_and_revoke_others(self):
        """``/sessions`` must resolve on its own route, not the ``session`` one."""
        match = resolve("/oidc/example/sessions")
        self.assertEqual(match.func.actions.get("get"), "sessions_list")
        self.assertEqual(match.func.actions.get("delete"), "sessions_revoke_others")
        self.assertNotIn("session", match.func.actions.values())

    def test_session_still_resolves_to_session_probe(self):
        """Anchoring ``session`` with ``$`` must not break the route itself."""
        match = resolve("/oidc/example/session")
        self.assertEqual(match.func.actions.get("get"), "session")

    def test_account_resolves_to_account_action(self):
        match = resolve("/oidc/example/account")
        self.assertEqual(match.func.actions.get("post"), "account")

    def test_linked_accounts_resolves_to_linked_list(self):
        match = resolve("/oidc/example/linked-accounts")
        self.assertEqual(match.func.actions.get("get"), "linked_list")

    def test_linked_accounts_link_url_resolves_to_linked_link_url(self):
        """The ``/link-url`` suffix route must win over the bare provider route."""
        match = resolve("/oidc/example/linked-accounts/foo/link-url")
        self.assertEqual(match.func.actions.get("get"), "linked_link_url")
        self.assertEqual(match.kwargs["provider"], "foo")

    def test_linked_accounts_provider_resolves_to_linked_unlink(self):
        match = resolve("/oidc/example/linked-accounts/foo")
        self.assertEqual(match.func.actions.get("delete"), "linked_unlink")
        self.assertEqual(match.kwargs["provider"], "foo")

    def test_sessions_id_resolves_to_sessions_revoke_one(self):
        match = resolve("/oidc/example/sessions/abc")
        self.assertEqual(match.func.actions.get("delete"), "sessions_revoke_one")
        self.assertEqual(match.kwargs["session_id"], "abc")
