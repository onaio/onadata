# -*- coding: utf-8 -*-
"""
Test google_tools module.
"""

from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from onadata.libs.utils.google_tools import create_flow


class CreateFlowTests(SimpleTestCase):
    """Tests for create_flow."""

    def test_autogenerate_code_verifier_is_explicitly_disabled(self):
        """
        The returned Flow must have PKCE code-verifier auto-generation
        explicitly turned off. The verifier is not persisted across the OAuth
        redirect, so any auto-generated verifier produces an authorization
        URL the callback cannot complete. Since the flow uses a confidential
        web client (client_secret), PKCE is not required.
        """
        flow = create_flow()

        self.assertIs(flow.autogenerate_code_verifier, False)

    def test_authorization_url_has_no_pkce_code_challenge(self):
        """The generated authorization URL must not carry PKCE params."""
        flow = create_flow()

        url, _state = flow.authorization_url()

        query = parse_qs(urlparse(url).query)
        self.assertNotIn("code_challenge", query)
        self.assertNotIn("code_challenge_method", query)

    def test_custom_redirect_uri_is_used(self):
        """An explicit redirect_uri overrides settings.GOOGLE_STEP2_URI."""
        custom = "https://example.test/oauth/callback"

        flow = create_flow(redirect_uri=custom)

        url, _state = flow.authorization_url()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query.get("redirect_uri"), [custom])
