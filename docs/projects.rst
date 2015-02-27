Projects
********

List, Retrieve, Update, Create Project and Project Forms

Where:

- ``pk`` - is the project id
- ``formid`` - is the form id
- ``owner`` - is the username for the user or organization of the project

Register a new Project
-----------------------
.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/projects</pre>

Example
^^^^^^^
::

       {
           "url": "https://ona.io/api/v1/projects/1",
           "owner": "https://ona.io/api/v1/users/ona",
           "name": "project 1",
           "date_created": "2013-07-24T13:37:39Z",
           "date_modified": "2013-07-24T13:37:39Z"
       }

List of Projects
-----------------

.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/projects</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects

Response
^^^^^^^^^
::

       [
           {
               "url": "https://ona.io/api/v1/projects/1",
               "owner": "https://ona.io/api/v1/users/ona",
               "name": "project 1",
               "date_created": "2013-07-24T13:37:39Z",
               "date_modified": "2013-07-24T13:37:39Z"
           },
           {
               "url": "https://ona.io/api/v1/projects/4",
               "owner": "https://ona.io/api/v1/users/ona",
               "name": "project 2",
               "date_created": "2013-07-24T13:59:10Z",
               "date_modified": "2013-07-24T13:59:10Z"
           }, ...
       ]

List of Projects filter by owner/organization
----------------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/projects?<code>owner</code>=<code>owner_username</code>
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects?owner=ona

Retrieve Project Information
--------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/projects/<code>{pk}</code></pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects/1

Response
^^^^^^^^
::

       {
           "url": "https://ona.io/api/v1/projects/1",
           "owner": "https://ona.io/api/v1/users/ona",
           "name": "project 1",
           "date_created": "2013-07-24T13:37:39Z",
           "date_modified": "2013-07-24T13:37:39Z"
       }

Update Project Information
------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/projects/<code>{pk}</code> or <b>PATCH</b> /api/v1/projects/<code>{pk}</code></pre></pre>

Example
^^^^^^^^
::

        curl -X PATCH -d 'metadata={"description": "Lorem ipsum","location": "Nakuru, Kenya","category": "water"}' https://ona.io/api/v1/projects/1

Response
^^^^^^^^^
::

    {
        "url": "https://ona.io/api/v1/projects/1",
        "owner": "https://ona.io/api/v1/users/ona",
        "name": "project 1",
        "metadata": {
            "description": "Lorem ipsum",
            "location": "Nakuru, Kenya",
            "category": "water"
        },
        "date_created": "2013-07-24T13:37:39Z",
        "date_modified": "2013-07-24T13:37:39Z"
    }

Share a project with a specific user
-------------------------------------

You can share a project with a specific user by ``POST`` a payload with

- ``username`` of the user you want to share the form with and
- ``role`` you want the user to have on the project.Available roles are ``readonly``, ``dataentry``, ``editor``, ``manager``.

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/projects/<code>{pk}</code>/share
	</pre>

Example
^^^^^^^^
::

    curl -X POST -d username=alice -d role=readonly https://ona.io/api/v1/projects/1/share

Response
^^^^^^^^^
::

    HTTP 204 NO CONTENT

Send an email to users on project share
----------------------------------------

An email is only sent when the `email_msg` request variable is present.

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/projects/<code>{pk}</code>/share
	</pre>

Example
^^^^^^^^^
::

    curl -X POST -d username=alice -d role=readonly -d email_msg="I have shared the project with you" https://ona.io/api/v1/projects/1/share

Response
^^^^^^^^^
::
       HTTP 204 NO CONTENT

Remove a user from a project
-------------------------------
You can remove a specific user from a project using `POST` with payload:

- ``username`` of the user you want to remove
- ``role`` the user has on the project
- ``remove`` set remove to True

Example
^^^^^^^^
::

    curl -X POST -d "username=alice" -d "role=readonly" -d "remove=True" http://localhost:8000/api/v1/projects/1/share

Response
^^^^^^^^^
::

    HTTP 204 NO CONTENT

Assign a form to a project
----------------------------

To [re]assign an existing form to a project you need to ``POST`` a payload of ``formid=FORMID`` to the endpoint below.

.. raw:: html

	<pre class="prettyprint"><b>POST</b> /api/v1/projects/<code>{pk}</code>/forms</pre>

Example
^^^^^^^^
::

    curl -X POST -d '{"formid": 28058}' https://ona.io/api/v1/projects/1/forms -H "Content-Type: application/json"

Response
^^^^^^^^^
::

    {
        "url": "https://ona.io/api/v1/forms/28058",
        "formid": 28058,
        "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
        "id_string": "Birds",
        "sms_id_string": "Birds",
        "title": "Birds",
        "allows_sms": false,
        "bamboo_dataset": "",
        "description": "",
        "downloadable": true,
        "encrypted": false,
        "owner": "ona",
        "public": false,
        "public_data": false,
        "date_created": "2013-07-25T14:14:22.892Z",
        "date_modified": "2013-07-25T14:14:22.892Z"
    }

Upload XLSForm to a project
--------------------------------
.. raw:: html

    <pre class="prettyprint"><b>POST</b> /api/v1/projects/<code>{pk}</code>/forms</pre>

Example
^^^^^^^^
::

    curl -X POST -F xls_file=@/path/to/form.xls https://ona.io/api/v1/projects/1/forms

Response
^^^^^^^^^
::


       {
           "url": "https://ona.io/api/v1/forms/28058",
           "formid": 28058,
           "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
           "id_string": "Birds",
           "sms_id_string": "Birds",
           "title": "Birds",
           "allows_sms": false,
           "bamboo_dataset": "",
           "description": "",
           "downloadable": true,
           "encrypted": false,
           "owner": "ona",
           "public": false,
           "public_data": false,
           "date_created": "2013-07-25T14:14:22.892Z",
           "date_modified": "2013-07-25T14:14:22.892Z"
       }

Get forms for a project
---------------------------
.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/projects/<code>{pk}</code>/forms
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects/1/forms

Response
^^^^^^^^^
::

       [
           {
               "url": "https://ona.io/api/v1/forms/28058",
               "formid": 28058,
               "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
               "id_string": "Birds",
               "sms_id_string": "Birds",
               "title": "Birds",
               "allows_sms": false,
               "bamboo_dataset": "",
               "description": "",
               "downloadable": true,
               "encrypted": false,
               "owner": "ona",
               "public": false,
               "public_data": false,
               "date_created": "2013-07-25T14:14:22.892Z",
               "date_modified": "2013-07-25T14:14:22.892Z",
               "tags": [],
               "users": [
                   {
                       "role": "owner",
                       "user": "alice",
                       "permissions": ["report_xform", ...]
                   },
                   ...
               ]
           },
           ...
       ]

Get list of projects with specific tag(s)
------------------------------------------

Use the ``tags`` query parameter to filter the list of projects, ``tags`` should be
a comma separated list of tags.

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/projects?<code>tags</code>=<code>tag1,tag2</code></pre>

List projects tagged ``smart`` or ``brand new`` or both.
Request
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects?tag=smart,brand+new

Response
^^^^^^^^^
::

        HTTP 200 OK

       [
           {
               "url": "https://ona.io/api/v1/projects/1",
               "owner": "https://ona.io/api/v1/users/ona",
               "name": "project 1",
               "date_created": "2013-07-24T13:37:39Z",
               "date_modified": "2013-07-24T13:37:39Z"
           },
           ...
       ]


Get list of Tags for a specific Project
------------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/project/<code>{pk}</code>/labels
	</pre>

Request
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/projects/28058/labels

Response
^^^^^^^^
::

       ["old", "smart", "clean house"]

Tag a Project
--------------

A ``POST`` payload of parameter ``tags`` with a comma separated list of tags.

Examples
^^^^^^^^^

- ``animal fruit denim`` - space delimited, no commas
- ``animal, fruit denim`` - comma delimited

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/projects/<code>{pk}</code>/labels
	</pre>

Payload
::

    {"tags": "tag1, tag2"}

Remove a tag from a Project
-----------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/projects/<code>{pk}</code>/labels/<code>tag_name</code>
	</pre>

Request
^^^^^^^^
::

    curl -X DELETE https://ona.io/api/v1/projects/28058/labels/tag1

or to delete the tag "hello world"

::

    curl -X DELETE https://ona.io/api/v1/projects/28058/labels/hello%20world

Response
^^^^^^^^^
::

    HTTP 200 OK

Add a star to a project
--------------------------
.. raw:: html

	<pre class="prettypriProjectnt">
	<b>POST</b> /api/v1/projects/<code>{pk}</code>/star</pre>

Remove a star to a project
--------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/projects/<code>{pk}</code>/star</pre>

Get user profiles that have starred a project
----------------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/projects/<code>{pk}</code>/star</pre>
    
