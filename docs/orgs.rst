Organizations
*************

Register a new Organization
---------------------------

.. raw:: html

   <pre class="prettyprint"><b>POST</b> /api/v1/orgs</pre>

Example
^^^^^^^

::

    {
        "org": "modilabs",
        "name": "Modi Labs Research",
        "email": "modilabs@localhost.com",
        "city": "New York",
        "country": "US",
        ...
    }

List of Organizations
---------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs</pre>

Example
^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/orgs

Response
^^^^^^^^

::

    [
        {
            "url": "https://api.ona.io/api/v1/orgs/modilabs",
            "org": "modilabs",
            "name": "Modi Labs Research",
            "email": "modilabs@localhost.com",
            "city": "New York",
            "country": "US",
            "website": "",
            "twitter": "",
            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
            "require_auth": false,
            "user": "https://api.ona.io/api/v1/users/modilabs",
            "creator": "https://api.ona.io/api/v1/users/demo"
        },
        ...
    ]

List of Organizations Shared with Another User
----------------------------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs?shared_with={username}</pre>


Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/orgs?shared_with=username


Get a paginated list of Organizations
-------------------------------------
Returns a list of organizations using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the ``page_size`` query param is 10,000

Organizations are listed alphabetically by their username (the ``org`` field). When neither parameter is supplied, the first 1,000 organizations are returned.

The response body remains a list. Links to the ``first``, ``prev``, ``next`` and ``last`` pages are returned in the ``Link`` response header, where they apply.

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs?<code>page</code>=<code>1</code>&<code>page_size</code>=<code>2</code></pre>

Example
^^^^^^^

::

      curl -X GET "https://api.ona.io/api/v1/orgs?page=1&page_size=2"

Response headers
^^^^^^^^^^^^^^^^

::

      Link: <https://api.ona.io/api/v1/orgs?page=2&page_size=2>; rel="next", <https://api.ona.io/api/v1/orgs?page=5&page_size=2>; rel="last"


Search Organizations
--------------------
Use the ``search`` parameter to return only the organizations whose name or username (the ``org`` field) contains the search term. The match is partial and not case sensitive. Only organizations the requesting user has access to are searched.

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs?<code>search</code>=<code>{term}</code></pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/orgs?search=health

``search`` can be combined with ``role``, ``shared_with``, ``page`` and ``page_size``.

Example
^^^^^^^

::

      curl -X GET "https://api.ona.io/api/v1/orgs?search=health&shared_with=username&page=1&page_size=20"


Filter Organizations by your role
---------------------------------
Use the ``role`` parameter to return only the organizations where you, the requesting user, hold that role or a higher one. For example, ``role=manager`` returns the organizations you manage or own.

``role`` accepts ``member`` and any role a member of an organization can be given: ``owner``, ``manager``, ``editor``, ``editor-minor``, ``editor-no-download``, ``dataentry``, ``dataentry-minor``, ``dataentry-only``, ``readonly`` and ``readonly-no-download``. Any other value returns a ``400`` error.

- ``owner`` - organizations you own.
- ``manager`` - organizations you manage or own.
- ``editor`` down to ``readonly`` - organizations where you have been given a role. These roles all carry the same access to an organization, so they return the same organizations. They are the ones where your ``role`` in the organization's ``users`` list is ``editor``, ``manager`` or ``owner``.
- ``member`` and ``readonly-no-download`` - every organization you belong to. This is the same as leaving ``role`` out.

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs?<code>role</code>=<code>{role}</code></pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/orgs?role=manager

``role`` can be combined with ``search``, ``shared_with``, ``page`` and ``page_size``.

Example
^^^^^^^

::

      curl -X GET "https://api.ona.io/api/v1/orgs?role=manager&search=health&page=1&page_size=20"


Retrieve Organization Profile Information
-----------------------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}</pre>


Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/orgs/modilabs


Response
^^^^^^^^

::

    {
        "url": "https://api.ona.io/api/v1/orgs/modilabs",
        "org": "modilabs",
        "name": "Modi Labs Research",
        "email": "modilabs@localhost.com",
        "city": "New York",
        "country": "US",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "user": "https://api.ona.io/api/v1/users/modilabs",
        "creator": "https://api.ona.io/api/v1/users/demo"
    }

Partial updates of Organization Profile Information
---------------------------------------------------

Organization profile properties can be updated using ``PATCH`` http
method. Payload required is for properties that are to be changed in
JSON, for example , ``{"metadata": {"computer": "mac"}}`` will set the
metadata to ``{"computer": "mac"}``.

.. raw:: html

   <pre class="prettyprint"><b>PATCH</b> /api/v1/orgs/{username}</pre>

Example
^^^^^^^

::

    curl -X PATCH -d ‘{“metadata”: {“computer”: “mac”}}’https://api.ona.io/api/v1/profiles/modilabs -H “Content-Type: application/json”

Response
^^^^^^^^

::

    {
        "url": "https://api.ona.io/api/v1/orgs/modilabs",
        "org": "modilabs",
        "name": "Modi Labs Research",
        "email": "modilabs@localhost.com",
        "city": "New York",
        "country": "US",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "metadata": {
            "computer": "mac"
        },
        "user": "https://api.ona.io/api/v1/users/modilabs",
        "creator": "https://api.ona.io/api/v1/users/demo"
   }

List Organization members
-------------------------

Get a list of organization members.

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}/members</pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/orgs/modilabs/members

Response
^^^^^^^^

::

      ["member1", "member2"]

Add a user to an organization
-----------------------------

To add a user to an organization requires a JSON payload of
``{"username": "member1"}``. You can add an optional parameter to define
the role of the user.\ ``{"username": "member1", "role": "editor"}``

.. raw:: html

   <pre class="prettyprint"><b>POST</b> /api/v1/orgs/{username}/members</pre>

Example
^^^^^^^

::

      curl -X POST -d '{"username": "member1"}' https://api.ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
^^^^^^^^

::

      ["member1"]

Send an email to a user added to an organization
------------------------------------------------

An email is only sent when the ``email_msg`` request variable is
present, ``email_subject`` is optional.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/orgs/{username}/members
   </pre>

Example
^^^^^^^

::

      curl -X POST -d '{"username": "member1", "email_msg": "You have been added to Ona", "email_subject": "Your have been added"}' https://api.ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
^^^^^^^^

::

       ["member1"]

Change the role of a user in an organization
--------------------------------------------

To change the role of a user in an organization pass the username and
role ``{"username": "member1", "role": "owner|manager|editor|dataentry|readonly"}``.

.. raw:: html

   <pre class="prettyprint"><b>PUT</b> /api/v1/orgs/{username}/members</pre>

Example
^^^^^^^

::

      curl -X PUT -d '{"username": "member1", "role": "editor"}' https://api.ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
^^^^^^^^

::

      ["member1"]

Remove a user from an organization
----------------------------------

To remove a user from an organization requires a JSON payload of
``{"username": "member1"}``.

.. raw:: html

   <pre class="prettyprint"><b>DELETE</b> /api/v1/orgs/{username}/members</pre>

Example
^^^^^^^

::

      curl -X DELETE -d '{"username": "member1"}' https://api.ona.io/api/v1/orgs/modilabs/members -H "Content-Type:application/json"

Response
^^^^^^^^

::

      []

Rotate a KMS key manually
-------------------------

.. raw:: html

   <pre class="prettyprint"><b>POST</b> /api/v1/orgs/{username}/rotate-key</pre>

Example
^^^^^^^

::

      curl -X POST https://api.ona.io/api/v1/orgs/modilabs/rotate-key \
      -d '{
            "id": "67",
            "rotation_reason": "Automatic rotation failed"
         }'


Response
^^^^^^^^

::

      {
          "id": "68",
          "description": "Key-2025-05-09",
          "date_created": "2025-05-09T00:00:00Z",
          "is_active": true,
          "is_expired": false,
          "expiry_date": "2026-05-09T00:00:00Z",
          "grace_end_date": "2026-06-09T00:00:00Z",
          "is_automatic": false,

      }
