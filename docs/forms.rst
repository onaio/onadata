Forms
******

Publish XLSForms, List, Retrieve Published Forms.
--------------------------------------------------

Where:

- ``pk`` - is the form unique identifier

Upload XLSForm
^^^^^^^^^^^^^^

To publish and xlsform, you need to provide either the xlsform via `xls_file` \
parameter or a link to the xlsform via the `xls_url` parameter.
Optionally, you can specify the target account where the xlsform should be \
published using the `owner` parameter, which specifies the username to the
account.

- ``xls_file``: the xlsform file.
- ``xls_url``: the url to an xlsform
- ``drop_xls_url``: the drop box url to an xlsform
- ``owner``: username to the target account (Optional)

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms</pre>

Example
^^^^^^^
::

    curl -X POST -F xls_file=@/path/to/form.xls https://ona.io/api/v1/forms

**OR post an xlsform url**
::

    curl -X POST -d "xls_url=https://ona.io/ukanga/forms/tutorial/form.xls" https://ona.io/api/v1/forms

**OR post an xlsform via Dropbox url**

::

    curl -X POST -d "dropbox_xls_url=https://www.dropbox.com/s/ynenld7xdf1vdlo/tutorial.xls?dl=1" https://ona.io/api/v1/forms

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

Get list of forms
------------------
.. raw:: html


	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms</pre>

Request
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms


Get list of forms filter by owner
----------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms?<code>owner</code>=<code>owner_username</code></pre>

Request
^^^^^^^
::

	curl -X GET https://ona.io/api/v1/forms?owner=ona


Get Form Information
---------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code></pre>

Example
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms/28058

Response
^^^^^^^^
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
           "owner": "https://ona.io/api/v1/users/ona",
           "public": false,
           "public_data": false,
           "require_auth": false,
           "date_created": "2013-07-25T14:14:22.892Z",
           "date_modified": "2013-07-25T14:14:22.892Z"
       }


Set Form Information
--------------------

You can use ``PUT`` or ``PATCH`` http methods to update or set form data elements.
If you are using ``PUT``, you have to provide the `uuid, description,
downloadable, owner, public, public_data, title` fields. With ``PATCH`` you only need to provide at least one of the fields.

- ``xls_file``: Can only be updated when there are no submissions.

.. raw:: html

	<pre class="prettyprint">
	<b>PATCH</b> /api/v1/forms/<code>{pk}</code></pre>

Example
^^^^^^^
::

       curl -X PATCH -d "public=True" -d "description=Le description" https://ona.io/api/v1/forms/28058

Response
^^^^^^^^
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
           "description": "Le description",
           "downloadable": true,
           "encrypted": false,
           "owner": "https://ona.io/api/v1/users/ona",
           "public": true,
           "public_data": false,
           "date_created": "2013-07-25T14:14:22.892Z",
           "date_modified": "2013-07-25T14:14:22.892Z"
       }

Delete Form
------------

.. raw:: html


	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/forms/<code>{pk}</code></pre>

Example
^^^^^^^
::

       curl -X DELETE https://ona.io/api/v1/forms/28058

Response
^^^^^^^^
::

       HTTP 204 NO CONTENT

Export form data asynchronously
-------------------------------

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/export_async
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms/28058/export_async?fmt=xls

Response
^^^^^^^^
::

       HTTP 202 Accepted
       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}

You can use the `job_uuid` value to check the progress of data export

Check progress of exporting form data asynchronously
-----------------------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/export_async?job_uuid=UUID
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms/28058/export_async?job_uuid=d1559e9e-5bab-480d-9804-e32111e8b2b8

Response
^^^^^^^^
If the job is done:

::

       HTTP 202 Accepted
       {
           "job_status": "SUCCESS",
           "export_url": "https://ona.io/api/v1/forms/28058.xls"
       }


Delete an XLS form asynchronously
-----------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms/<code>{pk}</code>/delete_async
	</pre>

Example
^^^^^^^
::

       curl -X DELETE https://ona.io/api/v1/forms/28058/delete_async

Response
^^^^^^^^

::

       HTTP 202 Accepted
       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}

You can use the ``job_uuid`` value to check on the upload progress (see below)

Check on XLS form deletion progress
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/delete_async?job_uuid=UUID
	</pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/delete_async?job_uuid=d1559e9e-5bab-480d-9804-e32111e8b2b8

Response
^^^^^^^^

If the job is done:

::

    HTTP 202 Accepted
    {"JOB_STATUS": "SUCCESS"}

List Forms
------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms
	</pre>

Example
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms

Response
^^^^^^^^
::

    [
        {
            "url": "https://ona.io/api/v1/forms/28058",
            "formid": 28058,
            "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
            "id_string": "Birds",
            "sms_id_string": "Birds",
            "title": "Birds",
            ...
        },
        ...
    ]


Get `JSON` | `XML` | `XLS` Form Representation
----------------------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/forms/<code>{pk}</code>/form.<code>{format}</code></pre>

JSON Example
^^^^^^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/form.json

Response
^^^^^^^^
::

        {
            "name": "Birds",
            "title": "Birds",
            "default_language": "default",
            "id_string": "Birds",
            "type": "survey",
            "children": [
                {
                    "type": "text",
                    "name": "name",
                    "label": "1. What is your name?"
                },
                ...
                ]
        }

XML Example
^^^^^^^^^^^
::

      curl -X GET https://ona.io/api/v1/forms/28058/form.xml

Response
^^^^^^^^
::

        <?xml version="1.0" encoding="utf-8"?>
        <h:html xmlns="http://www.w3.org/2002/xforms" ...>
          <h:head>
            <h:title>Birds</h:title>
            <model>
              <itext>
                 .....
          </h:body>
        </h:html>

XLS Example
^^^^^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/form.xls

Response
^^^^^^^^
     **XLS file downloaded**

Get list of forms with specific tag(s)
--------------------------------------

Use the ``tags`` query parameter to filter the list of forms, ``tags`` should be a
comma separated list of tags.

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms?<code>tags</code>=<code>tag1,tag2</code></pre>

List forms tagged ``smart`` or ``brand new`` or both.

Request
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms?tag=smart,brand+new

Response
^^^^^^^^
::

        HTTP 200 OK

Response
^^^^^^^^
::

    [
        {
            "url": "https://ona.io/api/v1/forms/28058",
            "formid": 28058,
            "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1f",
            "id_string": "Birds",
            "sms_id_string": "Birds",
            "title": "Birds",
            ...
        },
        ...
    ]


Get list of Tags for a specific Form
-------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/labels
	</pre>

Request
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/labels

Response
^^^^^^^^
::

      ["old", "smart", "clean house"]

Tag forms
---------

A ``POST`` payload of parameter ``tags`` with a comma separated list of tags.

Examples
^^^^^^^^

- ``animal fruit denim`` - space delimited, no commas
- ``animal, fruit denim`` - comma delimited

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms/<code>{pk}</code>/labels
	</pre>

Payload
::

    {"tags": "tag1, tag2"}

Delete a specific tag
------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/forms/<code>{pk}</code>/labels/<code>tag_name</code>
	</pre>

Request
^^^^^^^
::

    curl -X DELETE https://ona.io/api/v1/forms/28058/labels/tag1

or to delete the tag "hello world"

::

    curl -X DELETE https://ona.io/api/v1/forms/28058/labels/hello%20world

Response
^^^^^^^^
::

        HTTP 200 OK

Get webform/enketo link
------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/enketo</pre>

Request
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/enketo

Response
^^^^^^^^
::

    HTTP 200 OK

Response
^^^^^^^^^
::

    {
        "enketo_url": "https://h6ic6.enketo.org/webform",
        "enketo_preview_url": "https://H6Ic6.enketo.org/webform"
    }

Get webform/enketo link with default form values
-------------------------------------------------
.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/forms/<code>{pk}</code>/enketo?name=value</pre>

Request
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058/enketo?name=test

Response
^^^^^^^^
::

    HTTP 200 OK

Response
^^^^^^^^^
::

    {
        "enketo_url": "https://h6ic6.enketo.org/webform?d[%2Fform_id%2Fname]=test",
        "enketo_preview_url": "https://H6Ic6.enketo.org/webform/preview?server=https://ona.io/geoffreymuchai/&id=form_id"
    }


Get form data in xls, csv format.
---------------------------------

Get form data exported as xls, csv, csv zip, sav zip format.

Where:

- ``pk`` - is the form unique identifier
- ``format`` - is the data export format i.e csv, xls, csvzip, savzip

Params for the custom xls report

- ``meta``  - the metadata id containing the template url
-  ``token``  - the template url
-  ``data_id``  - the unique id of the submission

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/{pk}.{format}</code>
	</pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058.xls

Binary file export of the format specified is returned as the response for
the download.

Response
^^^^^^^^^
::

    HTTP 200 OK

Example 2 Custom XLS reports (beta)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/28058.xls?meta=12121

or

::

    curl -X GET https://ona.io/api/v1/forms/28058.xls?token={url}

XLS file is downloaded

Response
^^^^^^^^
::

        HTTP 200 OK

Example 3 Custom XLS reports with meta or token and data_id(beta)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/{pk}.{format}?{meta}&{data_id} -L -o {filename.xls}</code></pre>

::


    curl "https://ona.io/api/v1/forms/2.xls?meta=19&data_id=7" -L -o data.xlsx

or

::

    curl "https://ona.io/api/v1/forms/2.xls?token={url}&data_id=7" -L -o data.xlsx


XLS file is downloaded

Response
^^^^^^^^
::

    HTTP 200 OK

Get list of public forms
--------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/public
	</pre>

Share a form with a specific user
----------------------------------

You can share a form with a  specific user by `POST` a payload with

- ``username`` of the user you want to share the form with and
- ``role`` you want the user to have on the form. Available roles are ``readonly``, ``dataentry``, ``editor``, ``manager``.

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms/<code>{pk}</code>/share</pre>

Example
^^^^^^^
::

      curl -X POST -d '{"username": "alice", "role": "readonly"}' https://ona.io/api/v1/forms/123.json

Response
^^^^^^^^
::
       
    HTTP 204 NO CONTENT

Clone a form to a specific user account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can clone a form to a specific user account using `POST` with

- `username` of the user you want to clone the form to

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms/<code>{pk}</code>/clone
	</pre>

Example
^^^^^^^
::

       curl -X POST https://ona.io/api/v1/forms/123/clone -d username=alice

Response
^^^^^^^^
::

    HTTP 201 CREATED

Response
^^^^^^^^
::

    {
        "url": "https://ona.io/api/v1/forms/124",
        "formid": 124,
        "uuid": "853196d7d0a74bca9ecfadbf7e2f5c1e",
        "id_string": "Birds_cloned_1",
        "sms_id_string": "Birds_cloned_1",
        "title": "Birds_cloned_1",
        ...
    }

Import CSV data to existing form
---------------------------------

- `csv_file` a valid csv file with exported data (instance/submission per row)

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/forms/<code>{pk}</code>/csv_import
	</pre>

Example
^^^^^^^

::

    curl -X POST https://ona.io/api/v1/forms/123/csv_import -F csv_file=@/path/to/csv_import.csv

If the job was executed immediately:

Response
^^^^^^^^
::

    HTTP 200 OK
    {
        "additions": 9,
        "updates": 0
    }

If the import is a long running task:

Response
^^^^^^^^
::

    HTTP 200 OK
    {"job_uuid": "04874cee-5fea-4552-a6c1-3c182b8b511f"}

You can use the `job_uuid value to check on the import progres` (see below)

Check on CSV data import progress
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- `job_uuid` a valid csv import job_uuid returned by a long running import \
	previous call

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/forms/<code>{pk}</code>/csv_import?job_uuid=UUID
	</pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/forms/123/csv_import?job_uuid=UUID

Response
^^^^^^^^

If the job is done:

::

    HTTP 200 OK
    {
        "additions": 90000,
        "updates": 10000
    }

If the import is still running:

::

    HTTP 200 OK
    {
        "current": 100,
        "total": 100000
    }

Upload a XLS form async
-----------------------

.. raw:: html

	<pre class="prettyprint"><b>POST</b> /api/v1/forms/create_async</pre>


Example
^^^^^^^
::

      	curl -X POST https://ona.io/api/v1/forms/create_async -F xls_file=@/path/to/xls_file

Response
^^^^^^^^
::

    HTTP 202 Accepted
    {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}

You can use the `job_uuid value to check on the upload progress` (see below)

Check on XLS form upload progress
---------------------------------

.. raw:: html

	<pre class="prettyprint"><b>GET</b> /api/v1/forms/create_async/?job_uuid=UUID</pre>

Example
^^^^^^^
::

       curl -X GET https://ona.io/api/v1/forms/create_async?job_uuid=UUID

Response
^^^^^^^^

If the job is done:

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

If the upload is still running:

::

       HTTP 202 Accepted
       {
           "JOB_STATUS": "PENDING"
       }
