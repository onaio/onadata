"""
Test module for Open ID Connect tools
"""
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.openid_connect_tools import (EMAIL, LAST_NAME,
                                                     OpenIDHandler)

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
            EMAIL: 'sub',
            LAST_NAME: 'lname'
        },
        'end_session_endpoint': 'http://test.msft.oidc.com/oidc/logout',
        'scope': 'openid',
        'response_type': 'idtoken',
        'response_mode': 'form-post',
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

        # Test retrieves default values if claim is not set
        config = OPENID_CONNECT_PROVIDERS['msft']
        config.pop('claims')
        oidc_handler = OpenIDHandler(config)

        decoded_token = {
            'at_hash': 'mU342-Fsdsk',
            'sub': 'sdadasdasda',
            'amr': [
                "Basic Authenticator"
            ],
            'iss': 'http://test.msft.oidc.com/oauth2/token',
            'nonce': '12232',
            'email': 'some@email.com',
            'family_name': 'User',
            'given_name': 'Ted'
        }
        claim_values = oidc_handler.get_claim_values(
            ['email', 'given_name', 'family_name'], decoded_token)
        values = {
            'email': decoded_token.get('email'),
            'given_name': decoded_token.get('given_name'),
            'family_name': decoded_token.get('family_name')
        }
        self.assertEqual(values, claim_values)

    def test_make_login_request(self):
        """
        Test that the make_login_request function returns
        a HttpResponseRedirect object pointing to the correct
        url
        """
        response = self.oidc_handler.make_login_request(nonce=12323)
        expected_url = ('http://test.msft.oidc.com/authorize?nonce=12323'
                        '&client_id=test&redirect_uri=http://127.0.0.1:8000'
                        '/oidc/msft/callback&scope=openid&'
                        'response_type=idtoken&response_mode=form-post')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
