# -*- coding: utf-8 -*-
"""Authentication classes.
"""
from __future__ import unicode_literals

import jwt
from django.conf import settings
from django.core.signing import BadSignature
from django.db import DataError
from django.utils import timezone
from django.utils.translation import ugettext as _
from django_digest import HttpDigestAuthenticator
from django.shortcuts import get_object_or_404
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header
from rest_framework.authentication import BaseAuthentication
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.temp_token import TempToken
from onadata.libs.utils.common_tags import API_TOKEN

ENKETO_AUTH_COOKIE = getattr(settings, 'ENKETO_AUTH_COOKIE', '__enketo')
JWT_SECRET_KEY = getattr(settings, 'JWT_SECRET_KEY', 'jwt')
JWT_ALGORITHM = getattr(settings, 'JWT_ALGORITHM', 'HS256')
TEMP_TOKEN_EXPIRY_TIME = getattr(
    settings, 'DEFAULT_TEMP_TOKEN_EXPIRY_TIME', 60 * 60 * 6)


def expired(time_token_created):
    """Checks if the time between when time_token_created and current time
    is greater than the token expiry time.

    :params time_token_created: The time the token we are checking was created.
    :returns: Boolean True if not passed expired time, otherwise False.
    """
    time_diff = (timezone.now() - time_token_created).total_seconds()
    token_expiry_time = TEMP_TOKEN_EXPIRY_TIME

    return True if time_diff > token_expiry_time else False


def get_api_token(json_web_token):
    """Get API Token from JSON Web Token"""
    # having this here allows the values to be mocked easily as oppossed to
    # being on the global scope
    try:
        jwt_payload = jwt.decode(json_web_token,
                                 JWT_SECRET_KEY,
                                 algorithms=[JWT_ALGORITHM])
        api_token = get_object_or_404(
            Token, key=jwt_payload.get(API_TOKEN))

        return api_token
    except BadSignature as e:
        raise exceptions.AuthenticationFailed(_(u'Bad Signature: %s' % e))
    except jwt.DecodeError as e:
        raise exceptions.AuthenticationFailed(
            _(u'JWT DecodeError: %s' % e))


class DigestAuthentication(BaseAuthentication):
    """Digest authentication
    """

    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'digest':
            return None

        try:
            if self.authenticator.authenticate(request):
                return request.user, None
            else:
                raise AuthenticationFailed(
                    _('Invalid username/password'))
        except (AttributeError, ValueError, DataError) as e:
            raise AuthenticationFailed(e.message)

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response['WWW-Authenticate']


class TempTokenAuthentication(TokenAuthentication):
    """TempToken authentication using "Authorization: TempToken xxxx" header.
    """
    model = TempToken

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'temptoken':
            return None

        if len(auth) == 1:
            error_msg = _(u'Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(error_msg)
        elif len(auth) > 2:
            error_msg = _(u'Invalid token header. '
                          'Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(error_msg)

        return self.authenticate_credentials(auth[1])

    def authenticate_credentials(self, key):
        try:
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_(u'Invalid token'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(
                _(u'User inactive or deleted'))

        if expired(token.created):
            raise exceptions.AuthenticationFailed(_(u'Token expired'))

        return (token.user, token)

    def authenticate_header(self, request):
        return 'TempToken'


class EnketoTokenAuthentication(TokenAuthentication):
    """Enketo Token Authentication via JWT shared domain cookie name.
    """
    model = Token

    def authenticate(self, request):
        try:
            cookie_jwt = request.get_signed_cookie(
                ENKETO_AUTH_COOKIE,
                salt=getattr(settings, 'ENKETO_API_SALT')
            )
            api_token = get_api_token(cookie_jwt)

            if getattr(api_token, 'user'):
                return api_token.user, api_token
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_(u'Invalid token'))
        except KeyError:
            pass
        except BadSignature:
            # if the cookie wasn't signed it means zebra might have
            # generated it
            cookie_jwt = request.COOKIES.get(ENKETO_AUTH_COOKIE)
            api_token = get_api_token(cookie_jwt)
            if getattr(api_token, 'user'):
                return api_token.user, api_token

            raise exceptions.ParseError(
                _('Malformed cookie. Clear your cookies then try again'))

        return None


class TempTokenURLParameterAuthentication(TempTokenAuthentication):
    """TempToken URL via temp_token request parameter.
    """
    model = TempToken

    def authenticate(self, request):
        key = request.GET.get('temp_token')
        if not key:
            return None

        return self.authenticate_credentials(key)
