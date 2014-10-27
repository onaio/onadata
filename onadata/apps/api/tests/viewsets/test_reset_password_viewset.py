from mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.reset_password_viewset import \
    ResetPasswordViewSet


class TestResetPasswordViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = ResetPasswordViewSet.as_view({
            "post": "create"
        })

    @patch('onadata.apps.api.viewsets.reset_password_viewset.send_mail')
    def test_request_reset_password(self, mock_send_mail):
        data = {'email': self.user.email,
                'reset_url': u'http://testdomain.com/reset_form'}
        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(response.status_code, 200)

        mock_send_mail.called = False
        request = self.factory.post('/')
        response = self.view(request)
        self.assertFalse(mock_send_mail.called)
        self.assertEqual(response.status_code, 404)

    def test_reset_user_password(self):
        token = default_token_generator.make_token(self.user)
        new_password = "bobbob1"
        data = {'email':  self.user.email,
                'token': token,
                'new_password': new_password}

        request = self.factory.post('/', data=data)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.user.email)
        self.assertTrue(user.check_password(new_password))