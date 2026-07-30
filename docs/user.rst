User
****

Retrieve profile
================

Example
-------

::

      curl -X GET https://api.ona.io/api/v1/user

Response
--------

::

      {
            "api_token": "76121138a080c5ae94f318a8b9be91e7ebebb484",
            "temp_token": "0668993ad2f9fa6a0bff58389996cf85f11894ca"
            "city": "Nairobi",
            "country": "Kenya",
            "gravatar": "avatar.png",
            "name": "Demo User",
            "email": "demo@user.com",
            "organization": "",
            "require_auth": false,
            "twitter": "",
            "url": "http://api.ona.io/api/v1/profiles/demo",
            "user": "http://api.ona.io/api/v1/users/demo",
            "username": "demo",
            "website": "",

}

Get projects that the authenticating user has starred
=====================================================

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /api/v1/user/<code>{username}</code>/starred</pre>

Password reset
==============

Password resets are handled by the website's native flow, not the API.
Direct users who have forgotten their password to::

      /accounts/password/reset/

Submitting the form there emails the user a one-time link to
``/accounts/password/reset/confirm/<uid>/<token>/`` where a new password
can be set. Reset emails are rate limited per email address. Completing a
reset invalidates the user's existing API and temporary tokens.

Authenticated users can change their own password via
``POST /api/v1/profiles/{username}/change_password``.

Expire temporary token
======================

.. raw:: html

   <pre class="prettyprint">
   <b>DELETE</b> /api/v1/user/expire
   </pre>

-  Expires the temporary token

Example
-------

::

      curl -X DELETE https://api.ona.io/api/v1/user/expire

Response
--------

::

       HTTP 204 OK
