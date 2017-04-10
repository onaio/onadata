RestServices
************

This endpoint enables one to setup a rest service for a form.

- ``pk`` - primary key for the metadata
- ``formid`` - the form id for a form

.. note::
    Instances are sent to services asynchronously in the background. It is
    possible that an instance is never forwarded to the service if the
    instance is deleted before the background service task processes it.

Permissions
-----------

This endpoint applies the same permissions someone has on the form.

Post Payload
------------

The post data is a single json submission like it appears on the data endpoint.
It includes form fields and form metadata.

Example
::

    {
         "_id": 4503,
         "_bamboo_dataset_id": "",
         "_deleted_at": null,
         "expense_type": "service",
         "_xform_id_string": "exp",
         "_geolocation": [
             null,
             null
         ],
         "end": "2013-01-03T10:26:25.674+03",
         "start": "2013-01-03T10:25:17.409+03",
         "expense_date": "2011-12-23",
         "_status": "submitted_via_web",
         "today": "2013-01-03",
         "_uuid": "2e599f6fe0de42d3a1417fb7d821c859",
         "imei": "351746052013466",
         "formhub/uuid": "46ea15e2b8134624a47e2c4b77eef0d4",
         "kind": "monthly",
         "_submission_time": "2013-01-03T02:27:19",
         "required": "yes",
         "_attachments": [],
         "item": "Rent",
         "amount": "35000.0",
         "deviceid": "351746052013466",
         "subscriberid": "639027...60317"
     }


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
            service_url: "https://textit.in/api/v2/flow_starts.json"
        },
        ...
    ]

Get a specific Rest Service
---------------------------
.. raw:: html

	<pre class="prettyprint">
	GET /api/v1/restservices/<code>{pk}</code></pre>

::

    curl -X GET https://api.ona.io/api/v1/metadata/7100

::

    HTTP 200 OK

     {
            id: 236,
            xform: 9929,
            name: "textit",
            service_url: "https://textit.in/api/v2/flow_starts.json"
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
- google_sheets

Example:
^^^^^^^^
::

        curl -X POST -d "{"service_url": "https://textit.io/api/v2/flow_starts.json", "name":"textit", "xform": 9929}" https://api.ona.io/api/v1/restservices -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
            id: 236,
            xform: 9929,
            name: "textit",
            service_url: "https://textit.in/api/v2/flow_starts.json"
        }

Delete a Rest Service
---------------------
.. raw:: html

	<pre class="prettyprint">DELETE /api/v1/restservices/<code>{pk}</code></pre>


Adding TextIt
-------------
.. raw:: html

	<pre class="prettyprint">POST /api/v1/restservices</pre>

*Payload*
::

	{"auth_token": <auth_token>, "flow_uuid": "<flow_uuid>",
	"contacts": "<contacts>", "name": "textit",
	"service_url": "service_url", "xform": "xform"}

Where:

- ``auth_token`` - The authentication token for the rest service.
- ``flow_uuid`` - The flow uuid in textit.
- ``contacts`` - The contact used in the flow.
- ``service_url`` - The external url.
- ``name`` - Name of the supported service.
- ``xform`` - the form id you are adding the media to.

::

        curl -X POST -d "{"auth_token": "abffbbb8f16f7a1bc75f141b5aa538sasdsd", "flow_uuid":"cf7d7891-a01b-4ca9-99d2-weqqrwqd", "contacts": "52d4ff71-4d4e-464c-bksadfsdiwew", "name": "textit", "service_url":"https://textit.in/api/v2/flow_starts.json"}" https://api.ona.io/api/v1/restservices -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED

        {
            xform: 9929,
            auth_token: "abffbbb8f16f7a1bc75f141b5asdsadafc6d2d7d2b",
            flow_uuid: "cf7d7891-a01b-4ca9-9adssd-7baf5f77c741",
            contacts: "52d4ff71-4d4e-464c-asda-f0c04cc9e66d"
            id: 236,
            name: "textit",
            service_url: "https://textit.in/api/v2/flow_starts.json"
        }

Adding Google Sheet Sync
------------------------
.. raw:: html

	<pre class="prettyprint">POST /api/v1/restservices</pre>

*Payload*
::

        {
            "xform": 62548,
            "name": "google_sheets",
            "google_sheet_title": "population-sync",
            "send_existing_data": true,
            "sync_updates": false
        }

Where:

- ``google_sheet_title`` - Title of the google sheet sync file.
- ``send_existing_data`` - Boolean flag indicating whether existing data should be synced.
- ``sync_updates`` - Boolean flag indicating whether submission edits should be synced
- ``name`` - Service which is being configured.
- ``xform`` - The form id.

::

        curl -X POST -d "{"xform": 62548, "name": "google_sheets", "google_sheet_title": "population-sync","send_existing_data": true,"sync_updates": false}" https://api.ona.io/api/v1/restservices -H "Content-Type: appliction/json"

::

        HTTP 201 CREATED


Pushing Data To An Already linked Google Sheet
----------------------------------------------

Set send_existing_data to `true`
.. raw:: html

	<pre class="prettyprint">PATCH /api/v1/restservices/<code>pk</code></pre>

*Payload*
::

        {
            "xform": 62548,
            "name": "google_sheets",
            "google_sheet_title": "population-sync",
            "send_existing_data": true,
            "sync_updates": false
        }

Overiding The Default Google Oauth2 redirect_uri
------------------------------------------------

Add this `redirect_uri` and set your custom redirect url in the payload.

