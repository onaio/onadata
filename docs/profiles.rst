Profiles
********

Register a new User
-------------------

``username, email, first_name`` Are required fields. \ ``username`` may
contain alphanumeric, \_, @, +, . and - characters

.. raw:: html

   <pre class="prettyprint"><b>POST</b> /api/v1/profiles</pre>

Example
^^^^^^^

::

       {
           "username": "demo",
           "first_name": "Demo",
           "last_name": "User",
           "email": "demo@localhost.com",
           "city": "Kisumu",
           "country": "KE",
           ...
       }

List User Profiles
------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/profiles</pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/profiles

To retrieve a specific list of user profiles, an authenicated user should use ``users`` query param whose value
should be a comma-separated list of usernames as seen in the example below. A couple of things to note:

- Anonymous users will get an empty result.
- Authenticated users without the ``users`` query param will get their own profiles.

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/profiles?users=alice,bob,charlene

Response
^^^^^^^^

::

    [
        {
            "url": "https://api.ona.io/api/v1/profiles/demo",
            "username": "demo",
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo@localhost.com",
            "city": "",
            "country": "",
            "organization": "",
            "website": "",
            "twitter": "",
            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
            "require_auth": false,
            "user": "https://api.ona.io/api/v1/users/demo",
            "metadata": {},
            "joined_on": "2014-11-10T14:22:20.394Z"
        },
        ...
    ]

Retrieve User Profile Information
---------------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/profiles/{username}</pre>

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/profiles/{pk}</pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/profiles/demo

Response
^^^^^^^^

::

    {
        "url": "https://api.ona.io/api/v1/profiles/demo",
        "username": "demo",
        "first_name": "Demo",
        "last_name": "User",
        "email": "demo@localhost.com",
        "city": "",
        "country": "",
        "organization": "",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "user": "https://api.ona.io/api/v1/users/demo",
        "metadata": {},
        "joined_on": "2014-11-10T14:22:20.394Z"
    }


Partial updates of User Profile Information
-------------------------------------------

Properties of the UserProfile can be updated using ``PATCH`` http
method. Payload required is for properties that are to be changed in
JSON, for example, ``{"country": "KE"}`` will set the country to ``KE``.

.. raw:: html

   <pre class="prettyprint"><b>PATCH</b> /api/v1/profiles/{username}</pre>

Example
^^^^^^^

::

    curl -X PATCH -d ‘{"country": "KE"}’ https://api.ona.io/api/v1/profiles/demo -H "Content-Type: application/json"

Response
^^^^^^^^

::

    {
        "url": "https://api.ona.io/api/v1/profiles/demo",
        "username": "demo",
        "first_name": "Demo",
        "last_name": "User",
        "email": "demo@localhost.com",
        "city": "",
        "country": "KE",
        "organization": "",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "user": "https://api.ona.io/api/v1/users/demo",
        "metadata": {},
        "joined_on": "2014-11-10T14:22:20.394Z"
    }


Partial update for email requires password confirmation
-------------------------------------------------------

Example
^^^^^^^

::

    curl -X PATCH -d ‘{"email": "updated@email.com", "password": "password"}’ https://api.ona.io/api/v1/profiles/demo -H "Content-Type: application/json"


Partial update of the metadata profile property
-----------------------------------------------

This functionality allows for the updating of a key/value object of the
metadata property without overwriting the whole metadata property. For
example, if a user’s metadata was
``{"metadata": {"a": "Aaah", "b": "Baah"}}`` and we only wanted to
update ``b`` with value ``Beeh``, we would use this endpoing and add an
``overwrite`` param with value ``false``.

.. raw:: html

   <pre class="prettyprint"><b>PATCH</b> /api/v1/profiles/{username}</pre>

Example
^^^^^^^

::

    curl -X PATCH -d ‘{"metadata": {"b": "Beeh"}, "overwrite": "false"}’ https://api.ona.io/api/v1/profiles/demo -H "Content-Type: application/json"

Response
^^^^^^^^

::

    {
        "url": "https://api.ona.io/api/v1/profiles/demo",
        "username": "demo",
        "first_name": "Demo",
        "last_name": "User",
        "email": "demo@localhost.com",
        "city": "",
        "country": "KE",
        "organization": "",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "user": "https://api.ona.io/api/v1/users/demo"
        "metadata": {"a": "Aaah", "b": "Beeh"},
        "joined_on": "2014-11-10T14:22:20.394Z"
    }

Change authenticated user’s password
------------------------------------

Example
^^^^^^^

::

    curl -X POST -d current_password=password1 -d new_password=password2 https://api.ona.io/api/v1/profile/demouser/change_password

Response
^^^^^^^^

::

    HTTP 200 OK

Get the total number of monthly submissions
-------------------------------------------

This gets the total number of submissions made in a month to a specific user's forms.
The result is a count of the submissions to both private and public forms.

If there are no private forms then only the number of submissions to the public forms is returned, and vice versa.
If there are no submissions, then an empty dictionary is returned.

Use the month and year as query parameters to get the total number of submissions for a specific month.
If no query parameters are used, the result is the number of submissions of the current month.
If only month is used, then the year is assumed to be the current year. And if only year is passed, then the month is
assumed to be the current year.

Example
^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/profiles/demouser/monthly_submissions

Response
^^^^^^^^

::

    {
        "public": 41,
        "private": 185
    }

Example
^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/profiles/demouser/monthly_submissions?month=5&year=2018

Response
^^^^^^^^

::

    {
        "public": 240
    }

Email verification
-------------------------------------------

By default the email verification functionality is disabled. To enable this feature,
set ``ENABLE_EMAIL_VERIFICATION`` in your settings file to ``True``. ``VERIFIED_KEY_TEXT``
should also be set to ``ALREADY_ACTIVATED``. If you have a custom verification url that
you would prefer to be use instead of the default verification url, set it in ``VERIFICATION_URL``
settings variable. The verification url will be appended with the verificaiton key as query
param. Once ``ENABLE_EMAIL_VERIFICATION`` has been set, a verification email will be sent when
a new user is registered using the user profiles endpoint. The email verification endpoint expects
``verification_key`` query param as well as an optional ``redirect_url`` query param.

- ``verification_key`` - A REQUIRED query param which is a hexadecimal associated with a user that expires after 1 day. The expiration day limit can be changed by resetting the ``ACCOUNT_ACTIVATION_DAYS`` settings variable.
- ``redirect_url`` - An OPTIONAL query param that contains the url to redirect to when the ``verification_key`` has successfully been verified


Example
^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/profiles/verify_email?verification_key=abc&redirect_url=https://red.ir.ect


Successful Response
^^^^^^^^^^^^^^^^^^^

A succesful response or redirect includes 2 values:

- ``username`` - the account username of the verified email
- ``is_email_verified`` - the status of the verified email. It will be ``True`` for a successful response

if there is a redirect url, 2 query params will be appended to the url

::

    <redirect-url>?username=johndoe&is_email_verified=true

If there isn't a redirect url, the response will be

::

    {
        'username': 'johndoe',
        'is_email_verified': 'true'
    }




Failed Response
^^^^^^^^^^^^^^^

::

    Missing or invalid verification key

Send verification email
^^^^^^^^^^^^^^^^^^^^^^^

To send a verification email, for example when a user has changed his/her email address, the user making the request should
authenticate and provide ``username`` - which should be the same as the user making the request - in the post data. The
requesting user can also provide ``redirect_url`` as part of the post data. The ``redirect_url`` will be appended as query
param to the verification url and used to redirect the user to that url once the ``verification_key`` has successfully been verified.

Example
^^^^^^^

::

    curl -X POST -d username=johndoe -d redirect_url="https://red.ir.ect" https://api.ona.io/api/v1/profiles/send_verification_email


Successful Response
^^^^^^^^^^^^^^^^^^^

::

    Verification email has been sent

Failed Response
^^^^^^^^^^^^^^^

::

    Verification email has NOT been sent
