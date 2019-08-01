# -*- coding: utf-8 -*-
"""Authentication classes.
"""
from __future__ import unicode_literals

from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.signing import BadSignature
from django.db import DataError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import ugettext as _

import jwt
from django_digest import HttpDigestAuthenticator
from multidb.pinning import use_master
from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    TokenAuthentication,
    get_authorization_header,
)
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed

from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.api.tasks import send_account_lockout_email
from onadata.libs.utils.cache_tools import (
    LOCKOUT_USER,
    LOGIN_ATTEMPTS,
    cache,
    safe_key,
)
from onadata.libs.utils.common_tags import API_TOKEN
from onadata.libs.utils.email import get_account_lockout_email_data

ENKETO_AUTH_COOKIE = getattr(settings, "ENKETO_AUTH_COOKIE", "__enketo")
JWT_SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "jwt")
JWT_ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")
TEMP_TOKEN_EXPIRY_TIME = getattr(
    settings, "DEFAULT_TEMP_TOKEN_EXPIRY_TIME", 60 * 60 * 6
)


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
        jwt_payload = jwt.decode(
            json_web_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        api_token = get_object_or_404(Token, key=jwt_payload.get(API_TOKEN))

        return api_token
    except BadSignature as e:
        raise exceptions.AuthenticationFailed(_("Bad Signature: %s" % e))
    except jwt.DecodeError as e:
        raise exceptions.AuthenticationFailed(_("JWT DecodeError: %s" % e))


class DigestAuthentication(BaseAuthentication):
    """Digest authentication
    """

    def __init__(self):
        self.authenticator = HttpDigestAuthenticator()

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b"digest":
            return None

        try:
            check_lockout(request)
            if self.authenticator.authenticate(request):
                return request.user, None
            else:
                attempts = login_attempts(request)
                remaining_attempts = (
                    getattr(settings, "MAX_LOGIN_ATTEMPTS", 10) - attempts
                )
                raise AuthenticationFailed(
                    _(
                        "Invalid username/password. "
                        "For security reasons, after {} more failed "
                        "login attempts you'll have to wait {} minutes "
                        "before trying again.".format(
                            remaining_attempts,
                            getattr(settings, "LOCKOUT_TIME", 1800) // 60,
                        )
                    )
                )
        except (AttributeError, ValueError, DataError) as e:
            raise AuthenticationFailed(e)

    def authenticate_header(self, request):
        response = self.authenticator.build_challenge_response()

        return response["WWW-Authenticate"]


class TempTokenAuthentication(TokenAuthentication):
    """TempToken authentication using "Authorization: TempToken xxxx" header.
    """

    model = TempToken

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b"temptoken":
            return None

        if len(auth) == 1:
            error_msg = _("Invalid token header. No credentials provided.")
            raise exceptions.AuthenticationFailed(error_msg)
        elif len(auth) > 2:
            error_msg = _(
                "Invalid token header. "
                "Token string should not contain spaces."
            )
            raise exceptions.AuthenticationFailed(error_msg)

        return self.authenticate_credentials(auth[1])

    def authenticate_credentials(self, key):
        try:
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            invalid_token = True
            if getattr(settings, "SLAVE_DATABASES", []):
                try:
                    with use_master:
                        token = self.model.objects.get(key=key)
                except self.model.DoesNotExist:
                    invalid_token = True
                else:
                    invalid_token = False
            if invalid_token:
                raise exceptions.AuthenticationFailed(_("Invalid token"))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(
                _("User inactive or deleted")
            )

        if expired(token.created):
            raise exceptions.AuthenticationFailed(_("Token expired"))

        return (token.user, token)

    def authenticate_header(self, request):
        return "TempToken"


class EnketoTokenAuthentication(TokenAuthentication):
    """Enketo Token Authentication via JWT shared domain cookie name.
    """

    model = Token

    def authenticate(self, request):
        try:
            cookie_jwt = request.get_signed_cookie(
                ENKETO_AUTH_COOKIE, salt=getattr(settings, "ENKETO_API_SALT")
            )
            api_token = get_api_token(cookie_jwt)

            if getattr(api_token, "user"):
                return api_token.user, api_token
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid token"))
        except KeyError:
            pass
        except BadSignature:
            # if the cookie wasn't signed it means zebra might have
            # generated it
            cookie_jwt = request.COOKIES.get(ENKETO_AUTH_COOKIE)
            api_token = get_api_token(cookie_jwt)
            if getattr(api_token, "user"):
                return api_token.user, api_token

            raise exceptions.ParseError(
                _("Malformed cookie. Clear your cookies then try again")
            )

        return None


class TempTokenURLParameterAuthentication(TempTokenAuthentication):
    """TempToken URL via temp_token request parameter.
    """

    model = TempToken

    def authenticate(self, request):
        key = request.GET.get("temp_token")
        if not key:
            return None

        return self.authenticate_credentials(key)


def check_lockout(request):
    try:
        if isinstance(request.META["HTTP_AUTHORIZATION"], bytes):
            username = (
                request.META["HTTP_AUTHORIZATION"]
                .decode("utf-8")
                .split('"')[1]
            )
        else:
            username = request.META["HTTP_AUTHORIZATION"].split('"')[1]
    except (TypeError, AttributeError, IndexError):
        return
    else:
        lockout = cache.get(safe_key("{}{}".format(LOCKOUT_USER, username)))
        if lockout:
            time_locked_out = datetime.now() - datetime.strptime(
                lockout, "%Y-%m-%dT%H:%M:%S"
            )
            remaining_time = round(
                (
                    getattr(settings, "LOCKOUT_TIME", 1800)
                    - time_locked_out.seconds
                )
                / 60
            )
            raise AuthenticationFailed(
                _(
                    "Locked out. Too many wrong username/password attempts. "
                    "Try again in {} minutes.".format(remaining_time)
                )
            )
        return username


def login_attempts(request):
    """Track number of login attempts made by user within a specified amount
     of time"""
    username = check_lockout(request)
    attempts_key = safe_key("{}{}".format(LOGIN_ATTEMPTS, username))
    attempts = cache.get(attempts_key)

    if attempts:
        cache.incr(attempts_key)
        attempts = cache.get(attempts_key)
        if attempts >= getattr(settings, "MAX_LOGIN_ATTEMPTS", 10):
            send_lockout_email(username)
            cache.set(
                safe_key("{}{}".format(LOCKOUT_USER, username)),
                datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                getattr(settings, "LOCKOUT_TIME", 1800),
            )
            check_lockout(request)
            return attempts
        return attempts

    cache.set(attempts_key, 1)

    return cache.get(attempts_key)


def send_lockout_email(username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        pass
    else:
        email_data = get_account_lockout_email_data(username)
        end_email_data = get_account_lockout_email_data(username, end=True)

        send_account_lockout_email.apply_async(
            args=[
                user.email,
                email_data.get("message_txt"),
                email_data.get("subject"),
            ]
        )
        # send end of lockout email 1 minute after lockout time
        send_account_lockout_email.apply_async(
            args=[
                user.email,
                end_email_data.get("message_txt"),
                end_email_data.get("subject"),
            ],
            countdown=getattr(settings, "LOCKOUT_TIME", 1800) + 60,
        )
