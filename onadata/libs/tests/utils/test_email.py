from django.test import RequestFactory

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.email import get_verification_email_data


def get_kwargs(verification_url=None):
	request_factory = RequestFactory()
	request = request_factory.get('/path', data={'name': u'test'})

	return {
		"email": "john@doe.com",
		"username": "johndoe",
		"verification_key": "123abc",
		"verification_url": verification_url,
		"request": request
	}


class TestEmail(TestBase):

	def test_get_verification_email_data_without_verification_url(self):
		kwargs = get_kwargs()
		email_data = get_verification_email_data(**kwargs)

		self.assertIn(
			('http://testserver/api/v1/profiles/verify_email?'
			 'verification_key=123abc'),
			email_data.get('message_txt')
		)

	def test_get_verification_email_data_with_verification_url(self):
		verification_url = "http://ab.cd.ef"
		kwargs = get_kwargs(verification_url)
		email_data = get_verification_email_data(**kwargs)
		self.assertIn(
			'%s?verification_key=123abc' % verification_url,
		    email_data.get('message_txt')
		)

