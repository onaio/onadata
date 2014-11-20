from django.utils.translation import ugettext as _
from django_digest import HttpDigestAuthenticator
from rest_framework.authentication import get_authorization_header
from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import exceptions
from onadata.apps.api.models.temp_token import TempToken
from django.utils import timezone


class DigestAuthentication(BaseAuthentication):

    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'digest':
            return None

        if self.authenticator.authenticate(request):
            return request.user, None
        else:
            raise AuthenticationFailed(
                _(u"Invalid username/password"))

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response['WWW-Authenticate']


class TempTokenAuthentication(TokenAuthentication):
    model = TempToken

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'temptoken':
            return None

        if len(auth) == 1:
            m = 'Invalid token header. No credentials provided.'
            raise exceptions.AuthenticationFailed(m)
        elif len(auth) > 2:
            m = 'Invalid token header. Token string should not contain spaces.'
            raise exceptions.AuthenticationFailed(m)

        return self.authenticate_credentials(auth[1])

    def authenticate_credentials(self, key):
        try:
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted')

        def expired(time_now, time_token_created):
            time_diff = time_now - time_token_created
            return True if time_diff.seconds > 0 else False

        if expired(timezone.now(), token.created):
            raise exceptions.AuthenticationFailed('Token expired')

        return (token.user, token)

    def authenticate_header(self, request):
        return 'TempToken'
