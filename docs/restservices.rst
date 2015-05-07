RestServices
************

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
     }

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
        }

Delete a Rest Service
^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

	<pre class="prettyprint">DELETE /api/v1/restservices/<code>{pk}</code></pre>


Adding TextIt:
^^^^^^^^^^^^^^
.. raw:: html

	<pre class="prettyprint">POST /api/v1/restservices</pre>

*Payload*
::

	       {"auth_token": <auth_token>, "flow_uuid": "<flow_uuid>",
	       "contacts": "<contacts>", "name": "textit",
	        "service_url": "service_url", "xform": "xform"}

Where:

- ``service`` - Service which is being configured.
- ``auth_token`` - The authentication token for the rest service.
- ``flow_uuid`` - The flow uuid in textit.
- ``contacts`` - The contact used in the flow.
- ``service_url`` - The external url.
- ``name`` - Name of the supported service.
- ``xform`` - the form id you are adding the media to.

::

        curl -X POST -d "{"auth_token": "abffbbb8f16f7a1bc75f141b5aa538sasdsd", "flow_uuid":"cf7d7891-a01b-4ca9-99d2-weqqrwqd", "contacts": "52d4ff71-4d4e-464c-bksadfsdiwew", "service": "textit"}" https://ona.io/api/v1/restservices/236/textit -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
            xform: 9929,
            auth_token: "abffbbb8f16f7a1bc75f141b5asdsadafc6d2d7d2b",
            flow_uuid: "cf7d7891-a01b-4ca9-9adssd-7baf5f77c741",
            contacts: "52d4ff71-4d4e-464c-asda-f0c04cc9e66d"
            id: 236,
            name: "textit",
            service_url: "https://textit.in/api/v1/runs.json"
        }

