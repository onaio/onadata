from django.utils.translation import ugettext as _
from django_digest import HttpDigestAuthenticator
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class DigestAuthentication(BaseAuthentication):
    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        if 'HTTP_AUTHORIZATION' in request.META:
            if self.authenticator.authenticate(request):
                return request.user, None
            else:
                raise AuthenticationFailed(
                    _(u"Invalid username or password supplied!"))

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response['WWW-Authenticate']
