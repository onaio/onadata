from mock import patch

from oauth2client.client import OAuth2WebServerFlow, OAuth2Credentials

from onadata.apps.api.tests.viewsets.test_abstract_viewset import (
    TestAbstractViewSet)
from onadata.apps.api.viewsets.google_viewset import GoogleViewSet
from onadata.apps.main.models import TokenStorageModel


class TestGoogleViewSet(TestAbstractViewSet):

    @patch.object(OAuth2WebServerFlow, 'step2_exchange')
    def test_google_auth(self, mock_oauth2):
        mock_oauth2.return_value = OAuth2Credentials("access_token",
                                                     "client_id",
                                                     "client_secret",
                                                     "refresh_token",
                                                     "token_expiry",
                                                     "token_uri", "user_agent")
        view = GoogleViewSet.as_view({
            'get': 'google_auth'
        })
        creds_count = TokenStorageModel.objects.filter(id=self.user.id).count()

        data = {'code': 'codeexample'}
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request)

        self.assertEqual(response.status_code, 201)

        current_creds = TokenStorageModel.objects.filter(id=self.user.id)\
            .count()
        self.assertEqual(creds_count + 1, current_creds)

    def test_google_auth_authenticated(self):
        view = GoogleViewSet.as_view({
            'get': 'google_auth'
        })
        creds_count = TokenStorageModel.objects.filter(id=self.user.id).count()

        data = {'code': 'codeexample'}
        # no authentication
        request = self.factory.get('/', data=data)
        response = view(request)

        self.assertEqual(response.status_code, 401)

        current_creds = TokenStorageModel.objects.filter(id=self.user.id) \
            .count()

        # creds not created
        self.assertEqual(creds_count, current_creds)
