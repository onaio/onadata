"""
Test OpenIDViewset module
"""
from django.test.utils import override_settings

from mock import patch

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.openid_connect_viewset import \
    OpenIDConnectViewSet

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
        'claims': {},
        'end_session_endpoint': 'http://test.msft.oidc.com/oidc/logout',
        'scope': 'openid',
        'response_type': 'idtoken',
        'response_mode': 'form-post',
    }
}


class TestOpenIDConnectViewSet(TestAbstractViewSet):
    """
    Test OpenIDConnectViewSet
    """

    def setUp(self):
        """
        Setup function for TestOpenIDConnectViewSet
        """
        super(self.__class__, self).setUp()
        self.view = OpenIDConnectViewSet.as_view({
            'get': 'callback',
            'post': 'callback'
        })

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    @patch(('onadata.apps.api.viewsets.openid_connect_viewset.'
            'OpenIDHandler.verify_and_decode_id_token'))
    def test_redirect_on_successful_authentication(self,
                                                   mock_get_decoded_id_token):
        """
        Test that user is redirected on successful authentication
        """
        mock_get_decoded_id_token.return_value = {
            'given_name': self.user_profile_data().get('first_name'),
            'family_name': self.user_profile_data().get('last_name'),
            'email': self.user_profile_data().get('email')
        }

        data = {'id_token': 123456}
        request = self.factory.post('/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 302)

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    @patch(('onadata.apps.api.viewsets.openid_connect_viewset.'
            'OpenIDHandler.verify_and_decode_id_token'))
    def test_redirect_non_existing_user_to_enter_username(
            self, mock_get_decoded_id_token):
        """
        Test that a none exisant user is redirected to the username setting
        page
        """
        mock_get_decoded_id_token.return_value = {
            'given_name': 'john',
            'family_name': 'doe',
            'email': 'john@doe.test'
        }

        data = {"id_token": 123456}
        request = self.factory.post(
            '/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Preferred Username",
                      response.rendered_content.decode('utf-8'))

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    @patch(('onadata.apps.api.viewsets.openid_connect_viewset.'
            'OpenIDHandler.verify_and_decode_id_token'))
    def test_trigger_error_on_existing_username(self,
                                                mock_get_decoded_id_token):
        """
        Test that an error is displayed on the rendered Username setting page
        when a user with the entered username exists
        """
        mock_get_decoded_id_token.return_value = {
            'given_name': 'john',
            'family_name': 'doe',
            'email': 'john@doe.test'
        }

        data = {
            "id_token": 123456,
            'username': self.user_profile_data().get('username')}
        request = self.factory.post('/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 200)
        self.assertIn(("The username provided already exists. "
                       "Please choose a different one"),
                      response.rendered_content.decode('utf-8'))

        # Should raise error for differently cased versions of the username
        data = {
            "id_token": 123456,
            'username': self.user_profile_data().get('username').upper()}
        request = self.factory.post('/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 200)
        self.assertIn(("The username provided already exists. "
                       "Please choose a different one"),
                      response.rendered_content.decode('utf-8'))

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    @patch(('onadata.apps.api.viewsets.openid_connect_viewset.'
            'OpenIDHandler.verify_and_decode_id_token'))
    def test_create_non_existing_user(self, mock_get_decoded_id_token):
        """
        Test that a user is created when the username is available and
        redirects to the target url after auth
        """
        mock_get_decoded_id_token.return_value = {
            'given_name': 'john',
            'family_name': 'doe',
            'email': 'john@doe.com'
        }
        data = {'id_token': 124, 'username': 'john'}
        request = self.factory.post('/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 302)

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    @patch(('onadata.apps.api.viewsets.openid_connect_viewset.'
            'OpenIDHandler.verify_and_decode_id_token'))
    def test_redirect_to_missing_detail_on_missing_email(
            self, mock_get_decoded_id_token):
        """
        Test that the user is redirected to the missing detail page when the
        email is not retrieved successfully
        """
        mock_get_decoded_id_token.return_value = {
            'given_name': 'john',
            'family_name': 'doe',
        }

        data = {"id_token": 123456, 'username': 'john'}
        request = self.factory.post(
            '/', data=data)
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Please set an email as an alias',
                      response.rendered_content.decode('utf-8'))

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    def test_400_on_unavailable_token(self):
        """
        Test a 400 is returned when a token is not available
        """
        request = self.factory.get('/')
        response = self.view(request, openid_connect_provider='msft')
        self.assertEqual(response.status_code, 400)

    @override_settings(OPENID_CONNECT_PROVIDERS=OPENID_CONNECT_PROVIDERS)
    def test_400_on_unconfigured_provider(self):
        """
        Test that the endpoint returns a 400 if the utilized provider
        is not configured
        """
        request = self.factory.get('/')
        response = self.view(request, openid_connect_provider='fake')
        self.assertEquals(response.status_code, 400)
