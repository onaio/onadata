Teams
*****

GET List of Teams
-----------------

Provides a json list of teams and the projects the team is assigned to.

Teams belong to an organization. Only owners and managers of the organization
can create its teams, update them, delete them, or change a team's membership.
Moving a team to another organization requires the requester to be an owner or
manager of both the current and the new organization. Granting or revoking a
team's role on a project additionally requires the requester to be an owner or
manager of that project.

.. raw:: html

   <pre class="prettyprint">
   <b>GET</b> /api/v1/teams
   </pre>

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/teams

Optional params:

-  ``org`` : Filter by organization.

Example
^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/teams?org=bruize

Response
^^^^^^^^

::

    [
        {
            "url": "https://api.ona.io/api/v1/teams/1",
            "name": "Owners",
            "organization": "bruize",
            "projects": []
        },
        {
            "url": "https://api.ona.io/api/v1/teams/2",
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

      curl -X GET https://api.ona.io/api/v1/teams/1

Response
^^^^^^^^

::

       {
           "url": "https://api.ona.io/api/v1/teams/1",
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

      curl -X GET https://api.ona.io/api/v1/teams/1/members

Response
^^^^^^^^

::

      ["member1"]

Create a team
-------------

POST ``{"name": "someteam", "organization": "orgusername"}`` to
``/api/v1/teams`` to create a team in an organization. The requester must be
an owner or manager of the organization; other callers receive
``403 FORBIDDEN``.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams
   </pre>

Example
^^^^^^^

::

      curl -X POST -d name="demo team" -d organization=bruize https://api.ona.io/api/v1/teams

Response
^^^^^^^^

::

       {
           "url": "https://api.ona.io/api/v1/teams/2",
           "name": "demo team",
           "organization": "bruize",
           "projects": []
       }

Add a user to a team
--------------------

POST ``{"username": "someusername"}`` to ``/api/v1/teams/<pk>/members``
to add a user to the specified team. A list of usernames is the response
for members of the team. Only owners and managers of the team's organization
can add or remove members; other callers receive ``403 FORBIDDEN``.

Members of the organization's ``Owners`` team hold owner permissions on the
organization. No other team grants those permissions, regardless of its name.

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
for all team members. The requester must be an owner or manager of the
project; other callers receive ``403 FORBIDDEN`` and no permissions change.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams/<code>{pk}</code>/share
   </pre>

Example
^^^^^^^

::

      curl -X POST -d project=3 -d role=readonly https://api.ona.io/api/v1/teams/1/share

Response
^^^^^^^^

::

       HTTP 204 NO CONTENT

Remove team default permissions on a project
--------------------------------------------

POST ``{"role":"readonly", "project": "project_id", "remove": "True"}``
to ``/api/v1/teams/<pk>/share`` to remove the default permissions on a
project for all team members. As with granting, the requester must be an
owner or manager of the project.

.. raw:: html

   <pre class="prettyprint">
   <b>POST</b> /api/v1/teams/<code>{pk}</code>/share
   </pre>

Example
^^^^^^^

::

      curl -X POST -d project=3 -d role=readonly -d remove=true https://api.ona.io/api/v1/teams/1/share

Response
^^^^^^^^

::

       HTTP 204 NO CONTENT
