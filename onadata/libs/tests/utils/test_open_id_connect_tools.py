"""
Test module for Open ID Connect tools
"""
from django.test.utils import override_settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.open_id_connect_tools import (OpenIDHandler)

OPENID_CONNECT_PROVIDERS = {
    'msft': {
        'authorization_endpoint': 'http://test.msft.oidc.com/authorize',
        'client_id': 'test',
        'client_secret': 'test',
        'jwks_endpoint': 'http://test.msft.oidc.com/jwks',
        'token_endpoint': 'http://test.msft.oidc.com/token',
        'callback_uri': 'http://127.0.0.1:8000/oidc/msft/callback',
        'target_url_after_auth': 'http://localhost:3000',
        'target_url_after_logout': 'http://localhost:3000',
        'domain_cookie': '',
        'claims': {
            'email': 'sub',
            'family_name': 'lname'
        },
        'end_session_endpoint': 'http://test.msft.oidc.com/oidc/logout',
        'scope': 'openid',
        'response_type': 'idtoken',
        'response_mode': '',
    }
}


class TestOpenIDConnectTools(TestBase):
    def setUp(self):
        self.oidc_handler = OpenIDHandler(OPENID_CONNECT_PROVIDERS['msft'])

    def test_gets_claim_values(self):
        """
        Test the the get_claim_values function returns the
        correct claim values
        """
        decoded_token = {
            'at_hash': 'mU342-Fsdsk',
            'sub': 'some@email.com',
            'amr': [
                "Basic Authenticator"
            ],
            'iss': 'http://test.msft.oidc.com/oauth2/token',
            'nonce': '12232',
            'lname': 'User',
            'given_name': 'Ted'
        }

        claim_values = self.oidc_handler.get_claim_values(
            ['email', 'given_name', 'family_name'], decoded_token)
        values = {
            'email': decoded_token.get('sub'),
            'given_name': decoded_token.get('given_name'),
            'family_name': decoded_token.get('lname')
        }
        self.assertEqual(values, claim_values)
