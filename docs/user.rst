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

Two kinds of request get the profile without ``api_token`` or
``temp_token``:

-  one authenticated with an OAuth access token
-  one authenticated with a password alone (Digest or Basic) for an account
   with two-factor authentication

Neither can call ``/api/v1/user/regenerate_auth_token`` or
``/api/v1/user/odk_token``; both answer **403**. An application gets only the
access its OAuth token was granted, and a password can't stand in for the
second factor. A two-factor account gets its tokens after signing in to the
website, or by calling the API with an existing token.

A client that signs users in by sending their username and password to
``/api/v1/user`` and then using the returned ``temp_token`` or ``api_token``
can't sign in a two-factor account: the response has no token to use. Such a
client should sign users in through the OAuth 2.0 Authorization Code flow or
single sign-on instead, which ask for the second factor. Until it does, it
should treat a response without ``temp_token`` as a failed sign-in and tell
the user why.

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
