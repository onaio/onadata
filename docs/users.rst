Users
*****

List Users
----------

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/users

Response
^^^^^^^^

::

      [
           {
               "username": "demo",
               "first_name": "First",
               "last_name": "Last"
           },
           {
               "username": "another_demo",
               "first_name": "Another",
               "last_name": "Demo"
           },
           ...
       ]

List Users excluding organizations
----------------------------------

Organizations are a type of user in the Ona API. To get all users excluding
organizations, set the `orgs` parameter to `false`. It is true by default.

Example
^^^^^^^

::
        curl -X GET https://api.ona.io/api/v1/users?orgs=false

Retrieve a specific user info
-----------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/users/{username}</pre>

Example
^^^^^^^

::

       curl -X GET https://api.ona.io/api/v1/users/demo

Response
^^^^^^^^

::

      {
          "username": "demo",
          "first_name": "First",
          "last_name": "Last"
      }

Search for a users using email
------------------------------

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/users?search=demo@email.com

Response
^^^^^^^^

::

       [
           {
               "username": "demo",
               "first_name": "First",
               "last_name": "Last"
           },
           {
               "username": "another_demo",
               "first_name": "Another",
               "last_name": "Demo"
           },
           ...
       ]
