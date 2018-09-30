import unittest
from django.test import RequestFactory
from django.test import Client
from django.conf import settings
from onadata.apps.main.views import CustomLoginView

if settings.USE_CUSTOM_LOGIN_TEMPLATE:
    class TestCustomLoginView(unittest.TestCase):
        def setUp(self):
            super(TestCustomLoginView, self).setUp()
            self.client = Client()
            self.factory = RequestFactory()
            request = (self.factory.get('registration:custom:login'))
            self.view = CustomLoginView()
            self.view.request = request
            self.response = CustomLoginView.as_view()(request)

        def test_get_context_data(self):
            # Issue a GET request.
            response = self.client.get('/accounts/login/')

            # Check that the response is 200 OK.
            self.assertEqual(response.status_code, 200)
            # Check that the rendered context contains links.
            self.assertEqual(response.context['ONA_LOGIN_LINK'], '/login/')
            self.assertEqual(response.context['ONA_PRIVACY_LINK'],
                             '/privacy.html/')
            self.assertEqual(response.context['ONA_TERMS_LINK'], '/tos.html/')
            self.assertEqual(response.context['PASSWORD_RESET_URL'],
                             '/request-password-reset/')
