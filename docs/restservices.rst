RestServices
****

This endpoint enable one to setup a rest service for a form.

- ``pk`` - primary key for the metadata
- ``formid`` - the form id for a form


Permissions
-----------

This endpoint applies the same permissions someone has on the form.


Get list of Rest Services
-------------------------

Returns a list of rest services across all forms requesting user has access to.

.. raw:: html

	<pre class="prettyprint">GET /api/v1/restservices</pre>

::

    HTTP 200 OK

    [
        {
            id: 236,
            xform: 9929,
            name: "textit",
            service_url: "https://textit.in/api/v1/runs.json"
        },
        ...
    ]
Get a specific Rest Service
---------------------------
.. raw:: html

	<pre class="prettyprint">
	GET /api/v1/restservices/<code>{pk}</code></pre>

::

    curl -X GET https://ona.io/api/v1/metadata/7100

::

    HTTP 200 OK

     {
            id: 236,
            xform: 9929,
            name: "textit",
            service_url: "https://textit.in/api/v1/runs.json"
     },
Add a Rest Service to a form
----------------------------
.. raw:: html

	<pre class="prettyprint">POST /api/v1/restservices</pre>

*Payload*
::

	       {"xform": <formid>, "service_url": "<service_url>",
	       "name": "<name>"}

Where:

- ``service_url`` - The external url.
- ``name`` - Name of the supported service.
- ``xform`` - the form id you are adding the media to.

Supported external services are:

- f2dhis2
- generic_json
- generic_xml
- bamboo
- textit

Example:
^^^^^^^^
::

        curl -X POST -d "{"service_url": "https://textit.io/api/v1/runs.json", "name":"textit", "xform": 9929}" https://ona.io/api/v1/restservices -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
            id: 236,
            xform: 9929,
            name: "textit",
            service_url: "https://textit.in/api/v1/runs.json"
        },
Delete a Rest Service
^^^^^^^^^^^^^^^^
.. raw:: html

	<pre class="prettyprint">DELETE /api/v1/restservices/<code>{pk}</code></pre>

Textit Rest Service
-------------------

This action adds, retrieves and delete metadata associated with the textit rest service.

Adding:
^^^^^^^^
.. raw:: html

	<pre class="prettyprint">POST /api/v1/restservices/<code>{pk}</code>/textit</pre>

*Payload*
::

	       {"auth_token": <auth_token>, "flow_uuid": "<flow_uuid>",
	       "contacts": "<contacts>"}

Where:

- ``auth_token`` - The authentication token for the rest service.
- ``flow_uuid`` - The flow uuid in textit.
- ``contacts`` - The contact used in the flow.
::

        curl -X POST -d "{"auth_token": "abffbbb8f16f7a1bc75f141b5aa538sasdsd", "flow_uuid":"cf7d7891-a01b-4ca9-99d2-weqqrwqd", "contacts": "52d4ff71-4d4e-464c-bksadfsdiwew""}" https://ona.io/api/v1/restservices/236/textit -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
            id: 39627,
            xform: 9929,
            data_value: "abffbbb8f16f7a1bc75f141b5aa538sasdsd|cf7d7891-a01b-4ca9-99d2-weqqrwqd|52d4ff71-4d4e-464c-bksadfsdiwew",
            data_type: "textit",
            data_file: "",
            data_file_type: null,
            url: "https://ona.io/api/v1/metadata/39627",
            file_hash: null
        }

Retrieving:
^^^^^^^^^^

::

        curl -X GET https://ona.io/api/v1/restservices/236/textit

::

        HTTP 200 OK

        {
            id: 39627,
            xform: 9929,
            data_value: "abffbbb8f16f7a1bc75f141b5aa538sasdsd|cf7d7891-a01b-4ca9-99d2-weqqrwqd|52d4ff71-4d4e-464c-bksadfsdiwew",
            data_type: "textit",
            data_file: "",
            data_file_type: null,
            url: "https://ona.io/api/v1/metadata/39627",
            file_hash: null
        }

Deleting
^^^^^^^^

::

    curl -X DELETE https://ona.io/api/v1/restservices/236/textit