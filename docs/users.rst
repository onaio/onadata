Users
*****

List Users
----------

Example
^^^^^^^

::

      curl -X GET https://ona.io/api/v1/users

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

Retrieve a specific user info
-----------------------------

.. raw:: html

   <pre class="prettyprint"><b>GET</b> /api/v1/users/{username}</pre>

Example
^^^^^^^

::

       curl -X GET https://ona.io/api/v1/users/demo

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

      curl -X GET https://ona.io/api/v1/users?search=demo@email.com

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
