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
