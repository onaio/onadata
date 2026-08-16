Authentication and Status Codes
*******************************

Status Codes
------------

-  **200** - Successful [``GET``, ``PATCH``, ``PUT``]
-  **201** - Resource successfully created [``POST``\ ]
-  **204** - Resouce successfully deleted [``DELETE``\ ]
-  **403** - Permission denied to resource
-  **404** - Resource was not found

Request based Authentication
----------------------------

Ona JSON API enpoints support both Basic authentication and API Token
Authentication through the ``Authorization`` header.

Basic Authentication
~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://api.ona.io/api/v1/ -u username:password

Token Authentication
~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://api.ona.io/api/v1/ -H "Authorization: Token TOKEN_KEY"

Temporary Token Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://api.ona.io/api/v1/ -H "Authorization: TempToken TOKEN_KEY"

The temporary token expires after ``DEFAULT_TEMP_TOKEN_EXPIRY_TIME`` seconds,
which defaults to 21600 seconds (6 hours). To expire the temporary token manually
use the `/user/expire` endpoint. Example using curl and password authentication:

::

    curl -X DELETE http://api.ona.io/api/v1/user/expire -u username:password

You could use another type of authentication as well.

To activate authentication via temporary token you must add the TemporaryToken
class to your local_settings.py file, for example:

::

    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
        'onadata.libs.authentication.DigestAuthentication',
        'onadata.libs.authentication.TempTokenAuthentication',
        ...

Using OAuth 2.0 with the Ona API
--------------------------------

Ona supports the OAuth 2.0 `Authorization Code flow
<https://www.rfc-editor.org/rfc/rfc6749#section-4.1>`_. Every public or
confidential client using this flow must use Proof Key for Code Exchange
(PKCE) with the ``S256`` challenge method.

1. Register your client application with Ona - `register`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  ``name`` - name of your application
-  ``client_type`` - select public or confidential as appropriate
-  ``authorization_grant_type`` - select Authorization code
-  ``redirect_uri`` - exact callback URL or URLs

Use a public client for software that cannot securely retain a client secret,
such as a browser-based, native, or command-line application. A public client
uses its ``client_id`` without a ``client_secret``. A confidential client must
retain its ``client_secret`` securely and authenticate at the token endpoint.
Both client types must use PKCE S256.

.. _register: /o/applications/register/

2. Create a PKCE verifier and challenge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For each authorization request, generate a new cryptographically random
``code_verifier`` containing 43 to 128 URI-unreserved characters. Keep the
verifier private until the token request. Derive the challenge as:

::

    code_challenge = BASE64URL(SHA256(ASCII(code_verifier)))

The base64url value must not contain ``=`` padding. For example, the verifier
and its derived challenge below are a matching pair from RFC 7636:

::

    code_verifier:  dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
    code_challenge: E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM

Do not reuse this example pair in an application.

3. Authorize the client application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Direct the user's browser to the authorization endpoint with the derived
challenge and the challenge method set to exactly ``S256``:

::

    https://api.ona.io/o/authorize/?client_id=CLIENT_ID&response_type=code&redirect_uri=https%3A%2F%2Fclient.example.org%2Foauth%2Fcallback&scope=read%20write&state=RANDOM_STATE&code_challenge=CODE_CHALLENGE&code_challenge_method=S256

Where:

-  ``client_id`` is the registered application ID
-  ``response_type`` must be ``code``
-  ``redirect_uri`` must exactly match a registered callback URL
-  ``state`` must be a random, transaction-specific value that the client
   validates after redirection
-  ``code_challenge`` is derived from the verifier for this transaction
-  ``code_challenge_method`` must be exactly ``S256``

Ona rejects Authorization Code requests with a missing challenge, an omitted
challenge method, ``plain``, or any unsupported challenge method.

The user signs in and approves the requested access. Ona then redirects the
browser to the registered callback URL:

::

    https://client.example.org/oauth/callback?state=RANDOM_STATE&code=AUTHORIZATION_CODE

The client must validate ``state`` before exchanging the authorization code.

4. Request an access token
~~~~~~~~~~~~~~~~~~~~~~~~~~

Exchange the authorization code at ``/o/token/``. The request must include the
original ``code_verifier``. A missing or incorrect verifier is rejected.

Public-client example:

::

    curl -X POST https://api.ona.io/o/token/ \
        --data-urlencode grant_type=authorization_code \
        --data-urlencode code=AUTHORIZATION_CODE \
        --data-urlencode client_id=CLIENT_ID \
        --data-urlencode redirect_uri=https://client.example.org/oauth/callback \
        --data-urlencode code_verifier=CODE_VERIFIER

A public client must not send a client secret. A confidential client sends the
same payload and also authenticates with HTTP Basic Authentication:

::

    curl -X POST https://api.ona.io/o/token/ \
        --user "CLIENT_ID:CLIENT_SECRET" \
        --data-urlencode grant_type=authorization_code \
        --data-urlencode code=AUTHORIZATION_CODE \
        --data-urlencode client_id=CLIENT_ID \
        --data-urlencode redirect_uri=https://client.example.org/oauth/callback \
        --data-urlencode code_verifier=CODE_VERIFIER

Response:

::

    {
        "access_token": "Q6dJBs9Vkf7a2lVI7NKLT8F7c6DfLD",
        "token_type": "Bearer", "expires_in": 36000,
        "refresh_token": "53yF3uz79K1fif2TPtNBUFJSFhgnpE",
        "scope": "read write groups"
    }

Where:

-  ``access_token`` - access token - expires
-  ``refresh_token`` - token to use to request a new ``access_token`` in
   case it has expired.

Now that you have an ``access_token`` you can make API calls.

5. Access the Ona API with the ``access_token``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://api.ona.io/api/v1 -H "Authorization: Bearer ACCESS_TOKEN"

Making CORS - Cross-Origin Resource Sharing - requests to the Ona API
----------------------------------------------------------------------
To find out more about CORS, you can read about it `here <http://www.html5rocks.com/en/tutorials/cors/>`__. The following is a javascript code snippet on how to make a CORS request.

.. code-block:: javascript

   var xhr = new XMLHttpRequest();
   xhr.withCredentials = false;
   xhr.open('GET', 'https://api.ona.io/api/v1/user', true);
   xhr.setRequestHeader('Content-Type', 'application/json');
   xhr.setRequestHeader('Authorization', 'Token TOKEN_KEY');
   xhr.send();


The following is a jquery code snippet on how to make a CORS request.

.. code-block:: javascript

   $.ajax({
       method: "GET",
       url: 'https://api.ona.io/api/v1/user',
       dataType: 'json',
       xhrFields: {
           withCredentials: false
       },
       headers: {
           'Authorization': 'Token TOKEN_KEY'
       },
   });

OpenID Connect Authentication
------------------------------

.. toctree::
   :maxdepth: 2

   open-id-connect
