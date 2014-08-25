from django.utils.translation import ugettext as _
from django_digest import HttpDigestAuthenticator
from rest_framework.authentication import (
    BaseAuthentication, get_authorization_header)
from rest_framework.exceptions import AuthenticationFailed


class DigestAuthentication(BaseAuthentication):
    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        # If it is a head request, let assume it is a digest auth request
        if not auth or auth[0].lower() != b'digest' \
                and request.method != 'HEAD':
            return None

        if self.authenticator.authenticate(request):
            return request.user, None
        else:
            raise AuthenticationFailed(
                _(u"Invalid username/password"))

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response['WWW-Authenticate']
