from mock import patch

from django.contrib.auth.models import User

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
        data = {'email': u'bob@columbia.edu',
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
        request = self.factory.get('/')
        response = self.view(request, user='bob')
        self.assertEqual(response.status_code, 200)

        token = response.data['token']
        uid = response.data['uid']
        new_password = "bobbob1"
        post_data = {'token': token,
                     'uid': uid,
                     'new_password': new_password}

        request = self.factory.post('/', user='bob', data=post_data)
        response = self.view(request, user='bob')
        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username__iexact=self.user.username)
        self.assertTrue(user.check_password(new_password))