.. Onadata API documentation master file, created by
   sphinx-quickstart on Fri Feb 20 10:58:27 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Ona API's documentation!
=======================================

Ona JSON Rest Api Endpoints
===========================

Data Endpoints
--------------

.. toctree::
   :maxdepth: 2

   charts
   data
   stats

Forms
-----

.. toctree::
   :maxdepth: 2

   forms
   media
   metadata
   projects
   submissions

Users and Organizations
-----------------------

.. toctree::
   :maxdepth: 2

   orgs
   profiles
   teams
   user
   users

Ona Tagging API
~~~~~~~~~~~~~~~

-  `Filter form list by tags.`_
-  `List Tags for a specific form.`_
-  `Tag Forms.`_
-  `Delete a specific tag.`_
-  `List form data by tag.`_
-  `Tag a specific submission`_

.. _Filter form list by tags.: forms.html#get-list-of-forms-with-specific-tags
.. _List Tags for a specific form.: forms.html#get-list-of-tags-for-a-specific-form
.. _Tag Forms.: forms.html#tag-forms
.. _Delete a specific tag.: forms.html#delete-a-specific-tag
.. _List form data by tag.: data.html#query-submitted-data-of-a-specific-form-using-tags
.. _Tag a specific submission: data.html#tag-a-submission-data-point

Authentication and Status Codes
===============================

Status Codes
------------

-  **200** - Successful [``GET``, ``PATCH``, ``PUT``]
-  **201** - Resource successfully created [``POST``\ ]
-  **204** - Resouce successfully deleted [``DELETE``\ ]
-  **403** - Permission denied to resource
-  **404** - Resource was not found

Authentication
--------------

Ona JSON API enpoints support both Basic authentication and API Token
Authentication through the ``Authorization`` header.

Basic Authentication
~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://ona.io/api/v1/ -u username:password

Token Authentication
~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://ona.io/api/v1/ -H "Authorization: Token TOKEN_KEY"

Temporary Token Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example using curl:

::

    curl -X GET https://ona.io/api/v1/ -H "Authorization: TempToken TOKEN_KEY"

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

    http://localhost:8000/o/authorize?client_id=e8&response_type=code&state=xyz

Note: Providing the url to any user will prompt for a password and
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
    redirect_uri=http://localhost:30000" "http://localhost:8000/o/token/"
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

    curl -X GET https://ona.io/api/v1 -H "Authorization: Bearer ACCESS_TOKEN"

Quick start
-----------

.. toctree::
   :maxdepth: 3

   viewsets
   quick_start

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
