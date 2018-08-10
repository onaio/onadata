import urllib

from django.test import RequestFactory
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.email import get_verification_email_data


def get_kwargs(verification_url=None, redirect_url=None):
    request_factory = RequestFactory()
    request = request_factory.get('/path', data={'name': u'test'})

    return {
        "email": "john@doe.com",
        "username": "johndoe",
        "verification_key": "123abc",
        "verification_url": verification_url,
        "redirect_url": redirect_url,
        "request": request
    }


class TestEmail(TestBase):

    def test_get_verification_email_data_without_verification_url(self):
        kwargs = get_kwargs()
        email_data = get_verification_email_data(**kwargs)

        self.assertIn(
            ('http://testserver/api/v1/profiles/verify_email?'
             'verification_key=%s' % kwargs.get('verification_key')),
            email_data.get('message_txt')
        )

    def test_get_verification_email_data_with_verification_url(self):
        verification_url = "http://ab.cd.ef"
        kwargs = get_kwargs(verification_url)
        email_data = get_verification_email_data(**kwargs)
        self.assertIn(
            '{}?verification_key={}'.format(
                verification_url,
                kwargs.get('verification_key')
            ),
            email_data.get('message_txt')
        )

    def test_get_verification_email_data_with_verification_and_redirect_urls(
            self):
        verification_url = "http://ab.cd.ef"
        redirect_url = "http://red.ir.ect"
        kwargs = get_kwargs(verification_url, redirect_url)
        email_data = get_verification_email_data(**kwargs)
        encoded_url = urllib.urlencode({
            'verification_key': kwargs.get('verification_key'),
            'redirect_url': redirect_url
        })
        self.assertIn(
            encoded_url.replace('&', '&amp;'), email_data.get('message_txt')
        )
