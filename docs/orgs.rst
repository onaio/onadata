Organizations
*************

Register a new Organization
---------------------------

.. raw:: html

   <pre class="prettyprint"><b>POST</b> /api/v1/orgs</pre>

Example
-------

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
-------

::

    curl -X GET https://ona.io/api/v1/orgs

Response
--------

::

    [
        {
            "url": "https://ona.io/api/v1/orgs/modilabs",
            "org": "modilabs",
            "name": "Modi Labs Research",
            "email": "modilabs@localhost.com",
            "city": "New York",
            "country": "US",
            "website": "",
            "twitter": "",
            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
            "require_auth": false,
            "user": "https://ona.io/api/v1/users/modilabs",
            "creator": "https://ona.io/api/v1/users/demo"
        },
        ...
    ]

Retrieve Organization Profile Information
-----------------------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}</pre>

Example
-------

::

      curl -X GET https://ona.io/api/v1/orgs/modilabs

Response
--------

::

    {
        "url": "https://ona.io/api/v1/orgs/modilabs",
        "org": "modilabs",
        "name": "Modi Labs Research",
        "email": "modilabs@localhost.com",
        "city": "New York",
        "country": "US",
        "website": "",
        "twitter": "",
        "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
        "require_auth": false,
        "user": "https://ona.io/api/v1/users/modilabs",
        "creator": "https://ona.io/api/v1/users/demo"
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
-------

::

    curl -X PATCH -d ‘{“metadata”: {“computer”: “mac”}}’https://ona.io/api/v1/profiles/modilabs -H “Content-Type: application/json”

Response
--------

::

    {
        "url": "https://ona.io/api/v1/orgs/modilabs",
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
        "user": "https://ona.io/api/v1/users/modilabs",
        "creator": "https://ona.io/api/v1/users/demo"
   }

List Organization members
-------------------------

Get a list of organization members.

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}/members</pre>

Example
-------

::

      curl -X GET https://ona.io/api/v1/orgs/modilabs/members

Response
--------

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
-------

::

      curl -X POST -d '{"username": "member1"}' https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
--------

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
-------

::

      curl -X POST -d '{"username": "member1", "email_msg": "You have been added to Ona", "email_subject": "Your have been added"}' https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
--------

::

       ["member1"]

Change the role of a user in an organization
--------------------------------------------

To change the role of a user in an organization pass the username and
role ``{"username": "member1", "role": "owner|manager|editor|dataentry|readonly"}``.

.. raw:: html

   <pre class="prettyprint"><b>PUT</b> /api/v1/orgs/{username}/members</pre>

Example
-------

::

      curl -X PUT -d '{"username": "member1", "role": "editor"}' https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

Response
--------

::

      ["member1"]

Remove a user from an organization
----------------------------------

To remove a user from an organization requires a JSON payload of
``{"username": "member1"}``.

.. raw:: html

   <pre class="prettyprint"><b>DELETE</b> /api/v1/orgs/{username}/members</pre>

Example
-------

::

      curl -X DELETE -d '{"username": "member1"}' https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type:application/json"

Response
--------

::

      []
