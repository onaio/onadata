Teams
*****

GET List of Teams
-----------------

Provides a json list of teams and the projects the team is assigned to.

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /api/v1/teams
   </pre>

Example
^^^^^^^

::

      curl -X GET https://ona.io/api/v1/teams

Optional params:

-  ``org`` : Filter by organization.

Example
^^^^^^^

::

      curl -X GET https://ona.io/api/v1/teams?org=bruize

Response
^^^^^^^^

::

    [
        {
            "url": "https://ona.io/api/v1/teams/1",
            "name": "Owners",
            "organization": "bruize",
            "projects": []
        },
        {
            "url": "https://ona.io/api/v1/teams/2",
            "name": "demo team",
            "organization": "bruize",
            "projects": []
        }
    ]

GET Team Info for a specific team.
----------------------------------

Shows teams details and the projects the team is assigned to, where:

-  ``pk`` - unique identifier for the team

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /api/v1/teams/<code>{pk}</code>
   </pre>

Example
^^^^^^^

::

      curl -X GET https://ona.io/api/v1/teams/1

Response
^^^^^^^^

::

       {
           "url": "https://ona.io/api/v1/teams/1",
           "name": "Owners",
           "organization": "bruize",
           "projects": []
       }

List members of a team
----------------------

A list of usernames is the response for members of the team.

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /api/v1/teams/<code>{pk}/members</code>
   </pre>

Example
^^^^^^^

::

      curl -X GET https://ona.io/api/v1/teams/1/members

Response
^^^^^^^^

::

      ["member1"]

Add a user to a team
--------------------

POST ``{"username": "someusername"}`` to ``/api/v1/teams/<pk>/members``
to add a user to the specified team. A list of usernames is the response
for members of the team.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams/<code>{pk}</code>/members
   </pre>

Response
^^^^^^^^

::

      ["someusername"]

Set team default permissions on a project
-----------------------------------------

POST ``{"role":"readonly", "project": "project_id"}`` to
``/api/v1/teams/<pk>/share`` to set the default permissions on a project
for all team members.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams/<code>{pk}</code>/share
   </pre>

Example
^^^^^^^

::

      curl -X POST -d project=3 -d role=readonly https://ona.io/api/v1/teams/1/share

Response
^^^^^^^^

::

       HTTP 204 NO CONTENT

Remove team default permissions on a project
--------------------------------------------

POST ``{"role":"readonly", "project": "project_id", "remove": "True"}``
to ``/api/v1/teams/<pk>/share`` to remove the default permissions on a
project for all team members.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams/<code>{pk}</code>/share
   </pre>

Example
^^^^^^^

::

      curl -X POST -d project=3 -d role=readonly -d remove=true https://ona.io/api/v1/teams/1/share

Response
^^^^^^^^

::

       HTTP 204 NO CONTENT
