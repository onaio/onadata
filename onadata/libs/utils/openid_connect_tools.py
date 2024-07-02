# -*- coding: utf-8 -*-
"""
OpenID Connect Tools
"""
import json

from django.core.cache import cache
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import gettext as _

import jwt
import requests
from jwt.algorithms import RSAAlgorithm

EMAIL = "email"
NAME = "name"
FIRST_NAME = "given_name"
LAST_NAME = "family_name"
NONCE = "nonce"
DEFAULT_REQUEST_TIMEOUT = 30


class OpenIDHandler:
    """
    Base OpenID Connect Handler

    Implements functions neccessary to implement the OpenID Connect
    'code' or 'id_token' authorization flow
    """

    def __init__(self, provider_configuration: dict):
        """
        Initializes a OpenIDHandler Object to handle all OpenID Connect
        grant flows
        """

        self.provider_configuration = provider_configuration
        self.client_id = provider_configuration.get("client_id")
        self.client_secret = provider_configuration.get("client_secret")

    def make_login_request(self, nonce: int, state=None):
        """
        Makes a login request to the "authorization_endpoint" listed in the
        provider_configuration
        """
        if "authorization_endpoint" in self.provider_configuration:
            url = self.provider_configuration["authorization_endpoint"]
            url += f"?nonce={nonce}"

            if state:
                url += f"&state={state}"
        else:
            raise ValueError(
                "authorization_endpoint not found in provider configuration"
            )

        if "client_id" in self.provider_configuration:
            url += "&client_id=" + self.provider_configuration["client_id"]
        else:
            raise ValueError("client_id not found in provider configuration")

        if "callback_uri" in self.provider_configuration:
            url += "&redirect_uri=" + self.provider_configuration["callback_uri"]
        else:
            raise ValueError("client_id not found in provider configuration")

        if "scope" in self.provider_configuration:
            url += "&scope=" + self.provider_configuration["scope"]
        else:
            raise ValueError("scope not found in provider configuration")

        if "response_type" in self.provider_configuration:
            url += "&response_type=" + self.provider_configuration["response_type"]
        else:
            raise ValueError("response_type not found in provider configuration")

        if "response_mode" in self.provider_configuration:
            url += "&response_mode=" + self.provider_configuration["response_mode"]

        return HttpResponseRedirect(url)

    def get_claim_values(self, claim_list: list, decoded_token: dict):
        """
        Retrieves claim values from a decoded_token based on the claim name
        either configured in the provider configuration or the passed in
        claim

        :params
        claim_list: A list of strings containing the name of claim
        decoded_token: A dict containing the decoded values of an ID Token
        """
        claim_values = {}
        claim_names = self.provider_configuration.get("claims")

        for claim in claim_list:
            claim_name = claim

            if claim_names:
                if claim_names.get(claim):
                    claim_name = claim_names.get(claim)

            claim_values[claim] = decoded_token.get(claim_name)

        return claim_values

    def _retrieve_jwk_related_to_kid(self, kid):
        """
        Retrieves the JSON Web Key used to sign the ID Token
        from the JSON Web Key Set Endpoint
        """
        if "jwks_endpoint" not in self.provider_configuration:
            raise ValueError("jwks_endpoint not found in provider configuration")

        response = requests.get(
            self.provider_configuration["jwks_endpoint"],
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            jwks = response.json()
            for jwk in jwks.get("keys"):
                if jwk.get("kid") == kid:
                    return jwk

        return None

    def obtain_id_token_from_code(self, code: str, openid_provider: str = ""):
        """
        Obtain an ID Token using the Authorization Code flow
        """
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.provider_configuration.get("callback_uri"),
        }

        if "token_endpoint" not in self.provider_configuration:
            raise ValueError("token_endpoint not in provider configuration")

        response = requests.post(
            self.provider_configuration["token_endpoint"],
            params=payload,
            headers=headers,
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            id_token = response.json().get("id_token")
            return id_token

        retry_message = (
            "Failed to retrieve ID Token, "
            + f'<a href="/oidc/{openid_provider}">retry</a>'
            + "the authentication process"
        )
        raise Http404(_(retry_message))

    def verify_and_decode_id_token(
        self, id_token: str, cached_nonce: bool = False, openid_provider: str = ""
    ):
        """
        Verifies that the ID Token passed was signed and sent by the Open ID
        Connect Provider and that the client is one of the audiences then
        decodes the token and returns the decoded information
        """
        unverified_header = jwt.get_unverified_header(id_token)

        # Get public key thumbprint
        kid = unverified_header.get("kid")
        jwk = self._retrieve_jwk_related_to_kid(kid)

        if jwk:
            alg = unverified_header.get("alg")
            public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))

            decoded_token = jwt.decode(
                id_token, public_key, audience=[self.client_id], algorithms=alg
            )

            if cached_nonce:
                # Verify that the cached nonce is present and that
                # the provider the nonce was initiated for, is the same
                # provider returning it
                provider_initiated_for = cache.get(decoded_token.get(NONCE))

                if provider_initiated_for != openid_provider:
                    raise ValueError("Incorrect nonce value returned")
            return decoded_token

        return None

    def end_openid_provider_session(self):
        """
        Clears the SSO cookie set at authentication and redirects the User
        to the end_session endpoint provided by the provider configuration
        """
        end_session_endpoint = self.provider_configuration.get("end_session_endpoint")
        target_url_after_logout = self.provider_configuration.get(
            "target_url_after_logout"
        )

        response = HttpResponseRedirect(
            end_session_endpoint
            + "?post_logout_redirect_uri="
            + target_url_after_logout
        )
        response.delete_cookie("SSO")

        return response
