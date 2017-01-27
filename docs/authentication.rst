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

Using Oauth2 with the Ona API
-----------------------------

You can learn more about oauth2 `here`_.

1. Register your client application with Ona - `register`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  ``name`` - name of your application
-  ``client_type`` - Client Type: select confidential
-  ``authorization_grant_type`` - Authorization grant type: Authorization code
-  ``redirect_uri`` - Redirect urls: redirection endpoint

Keep note of the ``client_id`` and the ``client_secret``, it is required
when requesting for an ``access_token``.

.. _here: http://tools.ietf.org/html/rfc6749
.. _register: /o/applications/register/

2. Authorize client application.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The authorization url is of the form:

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /o/authorize?client_id=XXXXXX&response_type=code&state=abc</pre>

example:

::

    http://api.ona.io/o/authorize?client_id=e8&response_type=code&state=xyz

.. note::

  Providing the url to any user will prompt for a password and
  request for read and write permission for the application whose
  ``client_id`` is specified.

Where:

-  ``client_id`` - is the client application id - ensure its urlencoded
-  ``response_type`` - should be code
-  ``state`` - a random state string that you client application will
   get when redirection happens

What happens:

1. a login page is presented, the username used to login determines the
   account that provides access.
2. redirection to the client application occurs, the url is of the form:

    REDIRECT\_URI/?state=abc&code=YYYYYYYYY

example redirect uri

::

    http://localhost:30000/?state=xyz&code=SWWk2PN6NdCwfpqiDiPRcLmvkw2uWd

-  ``code`` - is the code to use to request for ``access_token``
-  ``state`` - same state string used during authorization request

Your client application should use the ``code`` to request for an
access\_token.

3. Request for access token.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You need to make a ``POST`` request with ``grant_type``, ``code``,
``client_id`` and ``redirect_uri`` as ``POST`` payload params. You
should authenticate the request with ``Basic Authentication`` using your
``client_id`` and ``client_secret`` as ``username:password`` pair.

Request:

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b>/o/token</pre>

Payload:

::

    grant_type=authorization_code&code=YYYYYYYYY&client_id=XXXXXX&redirect_uri=http://redirect/uri/path

curl example:

::

    curl -X POST -d "grant_type=authorization_code&
    code=PSwrMilnJESZVFfFsyEmEukNv0sGZ8&
    client_id=e8x4zzJJIyOikDqjPcsCJrmnU22QbpfHQo4HhRnv&
    redirect_uri=http://localhost:30000" "http://api.ona.io/o/token/"
    --user "e8:xo7i4LNpMj"

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
   case it has expored.

Now that you have an ``access_token`` you can make API calls.

4. Accessing the Ona API using the ``access_token``.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://api.ona.io/api/v1 -H "Authorization: Bearer ACCESS_TOKEN"

Making CORS - Cross-Origin Resource Sharing - requests to the Ona API
----------------------------------------------------------------------
To find out more about CORS, you can read about it `here <http://www.html5rocks.com/en/tutorials/cors/>`_. The following is a javascript code snippet on how to make a CORS request.

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
