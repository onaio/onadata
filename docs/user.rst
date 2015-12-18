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

Request password reset
======================

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/user/reset
   </pre>

-  Sends an email to the user’s email with a url that redirects to a reset password form on the API consumer’s website.
-  ``email`` and ``reset_url`` are expected in the POST payload ``email_subject`` is optional.
-  Expected reset\_url format is ``reset_url=https:/domain/path/to/reset/form``.
-  Example of reset url sent to user’s email is ``http://mydomain.com/reset_form?uid=Mg&token=2f3f334g3r3434&username=dXNlcg==``.
-  ``uid`` is the users ``unique key`` which is a base64 encoded integer value that can be used to access the users info at ``/api/v1/users/<pk>`` or ``/api/v1/profiles/<pk>``. You can retrieve the integer value in ``javascript`` using the ``window.atob();`` function. ``username`` is a base64 encoded value of the user’s username
-  ``token`` is a onetime use token that allows password reset

Example
-------

::

      curl -X POST -d email=demouser@mail.com -d reset\_url=http://example-url.com/reset https://api.ona.io/api/v1/user/reset -d email_subject="Reset password requested"

Response
--------

::

       HTTP 204 OK

Reset user password
===================

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/user/reset
   </pre>

-  Resets user’s password
-  ``uid``, ``token`` and ``new_password`` are expected in the POST payload.
-  minimum password length is 4 characters

Example
-------

::

      curl -X POST -d uid=Mg -d token=qndoi209jf02n4 -d new\_password=usernewpass https://api.ona.io/api/v1/user/reset

Response
--------

::

       HTTP 204 OK

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
