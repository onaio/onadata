import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import (
    HttpResponseBadRequest, HttpResponseRedirect)
from django.utils.translation import ugettext as _

import jwt
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response

from onadata.apps.main.models import UserProfile
from onadata.libs.utils.open_id_connect_tools import OpenIDHandler


class OpenIDConnectViewSet(viewsets.ViewSet):
    """
    OpenIDConnectViewSet: Handles OpenID connect authentication

    This OpenID Connect authentication flow requires the OpenID
    provider to provide the optional 'given_name', 'family_name' and 'email'
    claims in their payload
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    renderer_classes = (TemplateHTMLRenderer, )

    @action(methods=['GET'], detail=False)
    def initiate_oidc_flow(  # pylint: disable=no-self-use
            self, request, **kwargs):
        """
        This endpoint initiates the OpenID Connect Flow by generating a request
        to the OpenID Connect Provider with a cached none for verification of
        the returned request
        """
        provider_config, open_id_provider = retrieve_provider_config(
            **kwargs)

        if provider_config:
            nonce = secrets.randbits(16)
            cache.set(nonce, open_id_provider)

            return OpenIDHandler(provider_config).make_login_request(
                nonce=nonce)
        else:
            return HttpResponseBadRequest()

    @action(methods=['GET'], detail=False)
    def expire(self, request, **kwargs):  # pylint: disable=no-self-use
        """
        This endpoint ends an Open ID Connect
        authenticated user session
        """
        provider_config = retrieve_provider_config(
            **kwargs)[0]

        if provider_config:
            oidc_handler = OpenIDHandler(provider_config)
            return oidc_handler.end_open_id_provider_session()
        else:
            return HttpResponseBadRequest()

    @action(methods=['GET', 'POST'], detail=False)
    def callback(self, request, **kwargs):  # pylint: disable=no-self-use
        """
        This endpoint handles all callback requests made
        by an Open ID Connect Provider. Verifies that the request from the
        provider is valid and creates or gets a User
        """
        id_token = None
        user = None
        provider_config, open_id_provider = retrieve_provider_config(
            **kwargs)
        id_token = request.POST.get('id_token')
        data = {
            'logo_data_uri':
            getattr(settings, 'OIDC_LOGO_DATA_URI',
                    'https://ona.io/img/onadata-logo.png')
        }

        if not provider_config:
            return HttpResponseBadRequest()

        oidc_handler = OpenIDHandler(provider_config)

        if not id_token:
            # Use Authorization code if present to retrieve ID Token
            if request.query_params.get('code'):
                id_token = oidc_handler.obtain_id_token_from_code(
                    request.query_params.get('code'),
                    open_id_provider=open_id_provider)
            else:
                return HttpResponseBadRequest()

        data.update({"id_token": id_token})
        username = request.POST.get('username')
        decoded_token = oidc_handler.verify_and_decode_id_token(
            id_token, cached_nonce=True, open_id_provider=open_id_provider)

        if username:
            if get_user({"username": username}):
                error_msg = _("The username provided already exists. "
                              "Please choose a different one.")
                data = {'error_msg': error_msg, 'id_token': id_token}
            else:
                email = decoded_token.get('email')

                if not email:
                    data.update({
                        'missing_data':
                        'email',
                        'error_resolver':
                        'Please set an email as an alias on your Open ID' +
                        f' Connect providers({open_id_provider}) User page'
                    })
                    return Response(
                        data, template_name='missing_oidc_detail.html')

                first_name = decoded_token.get('given_name')
                last_name = decoded_token.get('family_name')
                user = create_or_get_user(first_name, last_name, email,
                                          username)
        else:
            user = get_user({'email': decoded_token.get('email')})

        if user:
            # On Successful login delete the cached nonce
            cache.delete(decoded_token.get('nonce'))

            return get_redirect_sso_response(
                redirect_uri=provider_config.get('target_url_after_auth'),
                email=user.email,
                domain=provider_config.get('domain_cookie'))
        elif data.get('id_token'):
            return Response(data, template_name='oidc_username_entry.html')
        else:
            return HttpResponseBadRequest()


def create_or_get_user(
        first_name: str, last_name: str, email: str, username: str):
    """
    This function creates or retrieves a User Object
    """
    user, created = User.objects.get_or_create(email=email,
                                               defaults={
                                                   'first_name': first_name,
                                                   'last_name': last_name,
                                                   'username': username
                                               })
    if created:
        UserProfile.objects.create(user=user)

    return user


def retrieve_provider_config(open_id_connect_provider: str):
    """
    This function retrieves a particular OpenID Connect providers
    provider_config
    """
    openid_connect_providers = getattr(settings, 'OPENID_CONNECT_PROVIDERS',
                                       None)

    if openid_connect_providers:
        return (openid_connect_providers.get(open_id_connect_provider),
                open_id_connect_provider)


def get_user(kwargs):
    """
    This function tries to retrieve a user using the passed in kwargs
    """
    return User.objects.filter(**kwargs).first()


def get_redirect_sso_response(
        redirect_uri: str, email: str, domain: str = None):
    """
    Returns an HttpResponseRedirect object and sets an
    Single Sign On (SSO) cookie to the object
    """
    value = jwt.encode({'email': email},
                       settings.JWT_SECRET_KEY,
                       algorithm=settings.JWT_ALGORITHM)
    redirect_response = HttpResponseRedirect(redirect_uri)
    redirect_response.set_cookie('SSO',
                                 value=value.decode('utf-8'),
                                 max_age=None,
                                 domain=domain)

    return redirect_response
