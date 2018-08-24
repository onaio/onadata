from future.moves.urllib.parse import urlencode

from django.test import RequestFactory
from django.test.utils import override_settings
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.email import (
    get_verification_email_data, get_verification_url
)

VERIFICATION_URL = "http://ab.cd.ef"


class TestEmail(TestBase):

    def setUp(self):
        self.email = "john@doe.com"
        self.username = "johndoe",
        self.verification_key = "123abc"
        self.redirect_url = "http://red.ir.ect"
        self.custom_request = RequestFactory().get(
            '/path', data={'name': u'test'}
        )

    @override_settings(VERIFICATION_URL=None)
    def test_get_verification_url(self):
        # without redirect_url
        verification_url = get_verification_url(**{
            "redirect_url": None,
            "request": self.custom_request,
            "verification_key": self.verification_key
        })

        self.assertEqual(
            verification_url,
            ('http://testserver/api/v1/profiles/verify_email?'
             'verification_key=%s' % self.verification_key),
        )

        # with redirect_url
        verification_url = get_verification_url(**{
            "redirect_url": self.redirect_url,
            "request": self.custom_request,
            "verification_key": self.verification_key
        })

        string_query_params = urlencode({
            'verification_key': self.verification_key,
            'redirect_url': self.redirect_url
        })

        self.assertEqual(
            verification_url,
            ('http://testserver/api/v1/profiles/verify_email?%s'
             % string_query_params)
        )

    def _get_email_data(self, include_redirect_url=False):
        verification_url = get_verification_url(**{
            "redirect_url": include_redirect_url and self.redirect_url,
            "request": self.custom_request,
            "verification_key": self.verification_key
        })

        email_data = get_verification_email_data(**{
            "email": self.email,
            "username": self.username,
            "verification_url": verification_url,
            "request": self.custom_request
        })

        self.assertIn('email', email_data)
        self.assertIn(self.email, email_data.get('email'))
        self.assertIn('subject', email_data)
        self.assertIn('message_txt', email_data)

        return email_data

    @override_settings(VERIFICATION_URL=None)
    def test_get_verification_email_data_without_verification_url_set(self):
        email_data = self._get_email_data()
        self.assertIn(
            ('http://testserver/api/v1/profiles/verify_email?'
             'verification_key=%s' % self.verification_key),
            email_data.get('message_txt')
        )

    @override_settings(VERIFICATION_URL=VERIFICATION_URL)
    def test_get_verification_email_data_with_verification_url_set(self):
        email_data = self._get_email_data()
        self.assertIn(
            '{}?verification_key={}'.format(
                VERIFICATION_URL, self.verification_key
            ),
            email_data.get('message_txt')
        )

    @override_settings(VERIFICATION_URL=VERIFICATION_URL)
    def test_get_verification_email_data_with_verification_and_redirect_urls(
            self):
        email_data = self._get_email_data(include_redirect_url=True)
        encoded_url = urlencode({
            'verification_key': self.verification_key,
            'redirect_url': self.redirect_url
        })
        self.assertIn(
            encoded_url.replace('&', '&amp;'), email_data.get('message_txt')
        )
