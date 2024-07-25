Projects
********

List, Retrieve, Update, Create Project and Project Forms

Where:

- ``pk`` - is the project id
- ``formid`` - is the form id
- ``owner`` - is the username for the user or organization of the project
- ``invitation_pk`` - is the project invitation id

Register a new Project
-----------------------
.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/projects</pre>

Example
^^^^^^^
::

       {
           "url": "https://api.ona.io/api/v1/projects/1",
           "owner": "https://api.ona.io/api/v1/users/ona",
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

       curl -X GET https://api.ona.io/api/v1/projects

Response
^^^^^^^^^
::

       [
           {
               "url": "https://api.ona.io/api/v1/projects/1",
               "owner": "https://api.ona.io/api/v1/users/ona",
               "name": "project 1",
               "date_created": "2013-07-24T13:37:39Z",
               "date_modified": "2013-07-24T13:37:39Z"
           },
           {
               "url": "https://api.ona.io/api/v1/projects/4",
               "owner": "https://api.ona.io/api/v1/users/ona",
               "name": "project 2",
               "date_created": "2013-07-24T13:59:10Z",
               "date_modified": "2013-07-24T13:59:10Z"
           }, ...
       ]

Get a paginated list of Projects
---------------------------------
Returns a list of projects using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page. The maximum number of items that can be requested in a page via the ``page_size`` query param is 10,000

.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/projects?<code>page</code>=<code>1</code><code>page_size</code>=<code>2</code></pre>

Example
^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/projects?page=1&page_size=2

Response
^^^^^^^^^
::

       [
           {
               "url": "https://api.ona.io/api/v1/projects/1",
               "owner": "https://api.ona.io/api/v1/users/ona",
               "name": "project 1",
               "date_created": "2013-07-24T13:37:39Z",
               "date_modified": "2013-07-24T13:37:39Z"
           },
           {
               "url": "https://api.ona.io/api/v1/projects/4",
               "owner": "https://api.ona.io/api/v1/users/ona",
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

You can use this to get both members and collaborators of an organization.
In the case of organizations, this gives you both members and collaborators under "users".
Under "teams" key we list only the members of the organization.

Example
^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/projects?owner=ona

Retrieve Project Information
--------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/projects/<code>{pk}</code></pre>

Example
^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/projects/1

Response
^^^^^^^^
::

        {
            "url":"https://api.ona.io/api/v1/projects/1",
            "projectid":1,
            "owner":"https://api.ona.io/api/v1/users/ona",
            "created_by":"https://api.ona.io/api/v1/users/ona",
            "metadata":{
                "name":"Entities",
                "category":"agriculture"
            },
            "starred":false,
            "users":[
                {
                    "is_org":false,
                    "metadata":{
                        "is_email_verified":false
                    },
                    "first_name":"Ona",
                    "last_name":"",
                    "user":"ona",
                    "role":"owner"
                }
            ],
            "forms":[
                {
                    "name":"Trees registration",
                    "formid":1,
                    "id_string":"trees_registration",
                    "num_of_submissions":7,
                    "downloadable":true,
                    "encrypted":false,
                    "published_by_formbuilder":null,
                    "last_submission_time":"2024-06-18T14:34:57.987361Z",
                    "date_created":"2024-05-28T12:08:07.993820Z",
                    "url":"https://api.ona.io/api/v1/forms/1",
                    "last_updated_at":"2024-06-21T08:13:06.436449Z",
                    "is_merged_dataset":false,
                    "contributes_entities_to":{
                        "id":100,
                        "name":"trees",
                        "is_active":true
                    },
                    "consumes_entities_from":[]
                },
                {
                    "name":"Trees follow-up",
                    "formid":18421,
                    "id_string":"trees_follow_up",
                    "num_of_submissions":0,
                    "downloadable":true,
                    "encrypted":false,
                    "published_by_formbuilder":null,
                    "last_submission_time":null,
                    "date_created":"2024-05-28T12:08:39.909235Z",
                    "url":"https://api.ona.io/api/v1/forms/2",
                    "last_updated_at":"2024-06-21T08:13:58.963836Z",
                    "is_merged_dataset":false,
                    "contributes_entities_to":null,
                    "consumes_entities_from":[
                        {
                            "id":100,
                            "name":"trees",
                            "is_active":true
                        }
                    ]
                }
            ],
            "public":false,
            "tags":[],
            "num_datasets":2,
            "last_submission_date":"2024-06-18T14:50:32.755792Z",
            "teams":[],
            "data_views":[],
            "name":"Entities",
            "date_created":"2023-11-07T07:02:09.655836Z",
            "date_modified":"2024-06-21T08:15:12.634454Z",
            "deleted_at":null
        }

Update Project Information
------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/projects/<code>{pk}</code> or <b>PATCH</b> /api/v1/projects/<code>{pk}</code></pre></pre>

Example
^^^^^^^^
::

        curl -X PATCH -d 'metadata={"description": "Lorem ipsum","location": "Nakuru, Kenya","category": "water"}' https://api.ona.io/api/v1/projects/1

Response
^^^^^^^^^
::

    {
        "url": "https://api.ona.io/api/v1/projects/1",
        "owner": "https://api.ona.io/api/v1/users/ona",
        "name": "project 1",
        "metadata": {
            "description": "Lorem ipsum",
            "location": "Nakuru, Kenya",
            "category": "water"
        },
        "date_created": "2013-07-24T13:37:39Z",
        "date_modified": "2013-07-24T13:37:39Z"
    }

Available Permission Roles
--------------------------
The following are the available roles in onadata:

- ``member`` Default role for user with no permission
- ``readonly-no-download`` Role for a user able to view data but not export it
- ``readonly`` Role for a user able to view and download data
- ``dataentry-only`` Role for a user able to submit data only
- ``dataentry-minor`` Role for a user able to submit and view only data he/she submitted
- ``dataentry`` Role for a user able to submit and view all data
- ``editor-minor`` Role for a user able to view and edit data he/she submitted
- ``editor`` Role for a user able to view and edit all data
- ``manager`` Role for a user with administrative privileges
- ``owner`` Role for an owner of a data-set, organization, or project.

Share a project with user(s)
-------------------------------------

You can share a project with a user or multiple users by ``PUT`` a payload with

- ``username`` of the user you want to share the form with or a list of users separated by a comma and
- ``role`` you want the user(s) to have on the project.Available roles are ``readonly``, ``dataentry``, ``editor``, ``manager``.

.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/projects/<code>{pk}</code>/share
	</pre>

Example 1: Sharing with a specific user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -X PUT -d username=alice -d role=readonly https://api.ona.io/api/v1/projects/1/share

Response
^^^^^^^^^
::

    HTTP 204 NO CONTENT

Example 2: Sharing with more than one user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -X PUT -d username=alice,jake -d role=readonly https://api.ona.io/api/v1/projects/1/share

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

    curl -X POST -d username=alice -d role=readonly -d email_msg="I have shared the project with you" https://api.ona.io/api/v1/projects/1/share

Response
^^^^^^^^^
::

       HTTP 204 NO CONTENT

Remove a user from a project
-------------------------------
You can remove a specific user from a project using `PUT` with payload:

- ``username`` of the user you want to remove
- ``role`` the user has on the project
- ``remove`` set remove to True

Example
^^^^^^^^
::

    curl -X PUT -d "username=alice" -d "role=readonly" -d "remove=True" http://api.ona.io/api/v1/projects/1/share

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

    curl -X POST -d '{"formid": 28058}' https://api.ona.io/api/v1/projects/1/forms -H "Content-Type: application/json"

Response
^^^^^^^^^
::

    {
        "url": "https://api.ona.io/api/v1/forms/28058",
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

    curl -X POST -F xls_file=@/path/to/form.xls https://api.ona.io/api/v1/projects/1/forms

Response
^^^^^^^^^
::


       {
           "url": "https://api.ona.io/api/v1/forms/28058",
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

       curl -X GET https://api.ona.io/api/v1/projects/1/forms

Response
^^^^^^^^^
::

       [
           {
               "url": "https://api.ona.io/api/v1/forms/28058",
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
                       ...
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

       curl -X GET https://api.ona.io/api/v1/projects?tag=smart,brand+new

Response
^^^^^^^^^
::

        HTTP 200 OK

       [
           {
               "url": "https://api.ona.io/api/v1/projects/1",
               "owner": "https://api.ona.io/api/v1/users/ona",
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

       curl -X GET https://api.ona.io/api/v1/projects/28058/labels

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

    curl -X DELETE https://api.ona.io/api/v1/projects/28058/labels/tag1

or to delete the tag "hello world"

::

    curl -X DELETE https://api.ona.io/api/v1/projects/28058/labels/hello%20world

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

Get Project Invitation List
---------------------------

.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/projects/{pk}/invitations</pre>

Example
^^^^^^^

::

        curl -X GET https://api.ona.io/api/v1/projects/1/invitations

Response
^^^^^^^^

::

        [
            {
                "id": 1,
                "email":"janedoe@example.com",
                "role":"readonly",
                "status": 1

            },
            {
                "id": 2,
                "email":"johndoe@example.com",
                "role":"editor",
                "status": 2,
            }
        ]

Get a list of project invitations with a specific status
--------------------------------------------------------

The available choices are:

- ``1`` - Pending. Invitations which have not been accepted by recipients.
- ``2`` - Accepted. Invitations which have been accepted by recipients.
- ``3`` - Revoked. Invitations which were cancelled.


.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/projects/{pk}/invitations?status=2</pre>


Example
^^^^^^^

::

        curl -X GET https://api.ona.io/api/v1/projects/1/invitations?status=2

Response
^^^^^^^^

::

        [

            {
                "id": 2,
                "email":"johndoe@example.com",
                "role":"editor",
                "status": 2,
            }
        ]


Create a new project invitation
-------------------------------

Invite an **unregistered** user to a project. An email will be sent to the user which has a link for them to
create an account.

.. raw:: html

	<pre class="prettyprint"><b>POST</b> /api/v1/projects/{pk}/invitations</pre>

Example
^^^^^^^

::

        curl -X POST -d "email=janedoe@example.com" -d "role=readonly" https://api.ona.io/api/v1/projects/1/invitations


``email``: The email address of the unregistered user.

- Should be a valid email. If the ``PROJECT_INVITATION_EMAIL_DOMAIN_WHITELIST`` setting has been enabled, then the email domain has to be in the whitelist for it to be also valid

**Example**

::

    PROJECT_INVITATION_EMAIL_DOMAIN_WHITELIST=["foo.com", "bar.com"]

- Email should not be that of a registered user

``role``: The user's role for the project.

- Must be a valid role


Response
^^^^^^^^

::

        {
            "id": 1,
            "email": "janedoe@example.com",
            "role": "readonly",
            "status": 1,
        }


The link embedded in the email will be of the format ``http://{url}``
where:

- ``url`` - is the URL the recipient will be redirected to on clicking the link. The default is ``{domain}/api/v1/profiles`` where ``domain`` is domain where the API is hosted.

Normally, you would want the email recipient to be redirected to a web app. This can be achieved by
adding the setting ``PROJECT_INVITATION_URL``

**Example**

::

    PROJECT_INVITATION_URL = {'*': 'https://example.com/register'}


Update a project invitation
---------------------------

.. raw:: html

	<pre class="prettyprint">
    <b>PUT</b> /api/v1/projects/{pk}/invitations
    </pre>


Example
^^^^^^^

::

        curl -X PUT -d "email=janedoe@example.com" -d "role=editor" -d "invitation_id=1"  https://api.ona.io/api/v1/projects/1/invitations/1

Response
^^^^^^^^

::

        {
            "id": 1,
            "email": "janedoe@example.com",
            "role": "editor",
            "status": 1,
        }


Resend a project invitation
---------------------------

Resend a project invitation email

.. raw:: html

	<pre class="prettyprint"><b>POST</b> /api/v1/projects/{pk}/resend-invitation</pre>

Example
^^^^^^^

::

        curl -X POST -d "invitation_id=6" https://api.ona.io/api/v1/projects/1/resend-invitation


``invitation_id``: The primary key of the ``ProjectInvitation`` to resend.

- Must be a ``ProjectInvitation`` whose status is **Pending**

Response
^^^^^^^^

::

        {
            "message": "Success"
        }

Revoke a project invitation
---------------------------

Cancel a project invitation. A revoked invitation means that project will **not** be shared with the new user
even if they accept the invitation.

.. raw:: html

	<pre class="prettyprint"><b>POST</b> /api/v1/projects/{pk}/revoke-invitation</pre>

Example
^^^^^^^

::

        curl -X POST -d "invitation_id=6" https://api.ona.io/api/v1/projects/1/revoke-invitation

``invitation_id``: The primary key of the ``ProjectInvitation`` to resend.

- Must be a ``ProjectInvitation`` whose status is **Pending**

Response
^^^^^^^^

::

        {
            "message": "Success"
        }


Accept a project invitation
---------------------------

Since a project invitation is sent to an unregistered user, acceptance of the invitation is handled
when `creating a new user <https://github.com/onaio/onadata/blob/main/docs/profiles.rst#register-a-new-user>`_.

All pending invitations whose email match the new user's email will be accepted and projects shared with the
user
