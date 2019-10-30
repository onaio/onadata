
OpenID Connect (Beta)
**********************

Overview
-------------

This endpoint provides the ability to authenticate users on onadata using an OpenID Connect provider, as such users can be created or logged in to the platform using OpenID Connect Providers such as Microsoft.

The OpenID Connect endpoint has only been tested with the Microsoft Platform.

When utilizing the OpenID Connect flow ensure the ``given_name``, ``family_name`` and ``email`` claims are available in the ID Token provided by the OpenID Connect provider.

Enabling OpenID Connect on onadata
-----------------------------------------------

In order to enable OpenID Connect authentication for a particular provider on the platform set the ``OPENID_CONNECT_PROVIDERS`` variable within your onadata ``local_settings.py``. The ``OPENID_CONNECT_PROVIDERS`` variable should be a ``dict``.

::

    {
        <provider_name>: {
            'authorization_endpoint': <authorization-endpoint>,
            'client_id': <client-id>,
            'client_secret': <client-secrete>,
            'jwks_endpoint': <json-web-key-set-endpoint>,
            'token_endpoint': <token-endpoint>,
            'callback_uri': <callback-url>,
            'target_url_after_auth': <target-url-after-authentication>,
            'target_url_after_logout': <target_url_after_logout>,
            'domain_cookie': <single-sign-on-cookie>,
            'end_session_endpoint': <end_session_endpoint>,
            'scope': <scope>,
            'response_type': <response_type>,
            'response_mode': <response_mode>,
        }
    }

Where:

-  ``<provider_name>`` - provider name or abbreaviation(utilized in ``/oidc/<provider_name>/callback`` and ``/oidc/<provide_name>/logout``
-  ``<authorization-endpoint>`` - url link to authorization endpoint, retrieved from chosen OpenID Connect providers OpenID configuration
-  ``<client_id>`` - Unique identifier for the applicaion, acquired from chosen OpenID connect provider
-  ``<client_secret>`` - Secret between onadata and the OpenID Connect provider, acquired from chosen OpenID connect provider
-  ``<jwks_endpoint>`` - url link to the JSON Web Key Set(JWKS), retrieved from chosen OpenID Connect providers OpenID configuration
-  ``<token_endpoint>`` - url link used to request for the ``id_token`` or ``code``, retrieved from chosen OpenID Connect providers OpenID configuration
-  ``<callback_uri>`` - url link set as the Callback URI on the OpenID Connect providers Application Registration, usually defaults to ``/oidc/<provider_name>/callback``.
-  ``<target_url_after_auth>`` - url to redirect to after a user has been authenicated on onadata.
-  ``<target_url_after_logout>`` - url to redirect to after a user has been successfully logged out from the Open ID Connect Provider ( This url must be a valid redirect uri on the Open ID Connect Providers Application Configuration )
-  ``<domain_cookie>`` - domain that the Single Sign On(SSO) cookie should be registered to
-  ``<end_session_endpoint>`` - url to call to end the Open ID Connect Providers session,
-  ``<scope>`` - a space-separated list of scopes, should include the ``openid`` scope,
-  ``<response_type>`` - type of response the OpenID Connect Provider should return on authorization. Valid types are ``code`` and ``id_token``.
-  ``<response_mode>`` - the method that should be used to send the resulting authorization code back to onadata the value should be ``form_post``,
