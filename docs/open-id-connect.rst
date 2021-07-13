
OpenID Connect (Beta)
**********************

Overview
-------------

This includes the ability to authenticate users on onadata using an OpenID Connect provider, as such users can be created or logged in to the platform using OpenID Connect Providers such as Microsoft.

The |OpenIDConnectlibrary| has currently only been tested with the Microsoft Platform.

.. |OpenIDConnectlibrary| raw:: html

    <a href="https://github.com/onaio/ona-oidc"
    target="_blank">OpenID Connect library</a>

When utilizing the OpenID Connect flow ensure the ``given_name``, ``family_name`` and ``email`` claims are available in the ID Token provided by the OpenID Connect provider.

Enabling OpenID Connect on onadata
----------------------------------

In order to enable OpenID Connect authentication for a particular provider on the platform set `OPENID_CONNECT_VIEWSET_CONFIG` and `OPENID_CONNECT_AUTH_SERVERS` variables within your onadata ``local_settings.py``.

::

    OPENID_CONNECT_VIEWSET_CONFIG = {
        "REDIRECT_AFTER_AUTH": "http://localhost:3000",
        "USE_SSO_COOKIE": True,
        "SSO_COOKIE_DATA": "email",
        "JWT_SECRET_KEY": JWT_SECRET_KEY,
        "JWT_ALGORITHM": JWT_ALGORITHM,
        "SSO_COOKIE_MAX_AGE": None,
        "SSO_COOKIE_DOMAIN": "localhost",
        "USE_AUTH_BACKEND": False,
        "AUTH_BACKEND": "",  # Defaults to django.contrib.auth.backends.ModelBackend
        "USE_RAPIDPRO_VIEWSET": False, 
    }

    OPENID_CONNECT_AUTH_SERVERS = {
        "microsoft": {
            "AUTHORIZATION_ENDPOINT": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "CLIENT_ID": "client_id",
            "JWKS_ENDPOINT": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
            "SCOPE": "openid profile",
            "RESPONSE_MODE": "form_post",
            "USE_NONCES": True
        }
    }

(Optional) If you would want to use cookie authentication, update the `REST_FRAMEWORK` settings.
::
    
    REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'onadata.libs.authentication.SSOHeaderAuthentication',
        ...,
        ),
    }
