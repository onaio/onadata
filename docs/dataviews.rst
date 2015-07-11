DataView
********

This endpoint provides access to filtered data from submitted XForm data.

Where:

- ``pk`` - is the dataview id

Definition
^^^^^^^^^^
- ``columns`` - Json list of columns to be included in the data
- ``query`` - Json list of dicts with filter information.

Each dict contains:

- ``column`` - The column the filter will be applied to.
- ``filter`` - The filter that will be used.
- ``value`` - The value to filter with.
- ``condition`` - (optional) This indicates which logical conjuction to use. Either ``AND``/``OR`` Default is ``AND``

Current Supported Filters

=======  ===================
Filter    Description
=======  ===================
**=**     Equal to
**>**     Greater than
**<**     Less than
**<=**    Less or Equal to
**>=**    Great or Equal to
**<>**    Not Equal to
**!=**    Not Equal to
=======  ===================

Example:
::

    {
        "column":"age",
        "filter":">",
        "value":"20",
        "condition":"or"
    }


Create a new DataView
^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/dataviews</pre>

Example
-------
::

        {
            'name': "My DataView",
            'xform': 'https://ona.io/api/v1/forms/12',
            'project':  'https://ona.io/api/v1/projects/13',
            'columns': '["name", "age", "gender"]',
            'query': '[{"column":"age", "filter":">", "value":"20"}]'
        }

Response
--------

::

        {
            name: "My DataView",
            url: "https://ona.io/api/v1/dataviews/1",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "20"
                }
            ]
        }


Retrieve a DataView
^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews/<code>{pk}</code></pre>

Response
--------

::

        {
            name: "My DataView",
            url: "https://ona.io/api/v1/dataviews/1",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "20"
                }
            ]
        }

List all DataView
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews</pre>

Response
--------

::


    [
        {
            name: "My DataView",
            url: "https://ona.io/api/v1/dataviews/1",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "20"
                }
            ]
        },
        {
            name: "My DataView2",
            url: "https://ona.io/api/v1/dataviews/2",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "30"
                }
            ]
        }
    ]


Update a DataView
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/dataviews/<code>{pk}</code></pre>

Example
-------
::

        {
            'name': "My DataView updated",
            'xform': 'https://ona.io/api/v1/forms/12',
            'project':  'https://ona.io/api/v1/projects/13',
            'columns': '["name", "age", "gender"]',
            'query': '[{"col":"age", "filter":">", "value":"30"}]'
        }

Response
--------

::

        {
            name: "My DataView updated",
            url: "https://ona.io/api/v1/dataviews/1",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "30"
                }
            ]
        }

Patch a DataView
^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PATCH</b> /api/v1/dataviews/<code>{pk}</code></pre>

Example
-------
::

        {
            'columns': '["name", "age", "gender", "date"]'
        }

Response
--------

::

        {
            name: "My DataView updated",
            url: "https://ona.io/api/v1/dataviews/1",
            xform: "https://ona.io/api/v1/forms/12",
            project: "https://ona.io/api/v1/projects/13",
            columns: [
                "name",
                "age",
                "gender",
                "date"
            ],
            query: [
                {
                    filter: ">",
                    column: "age",
                    value: "30"
                }
            ]
        }

Delete a DataView
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/dataviews/<code>{pk}</code></pre>

Response
--------

::

    HTTP 204 NO CONTENT


Retrieving Data from the DataView
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Returns the data using the dataview filters

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data
    </pre>

::

    curl -X GET 'https://ona.io/api/v1/dataviews/1/data'



Example Response
----------------
::


        [
                {"date": "2015-05-19", "gender": "male", "age": 32, "name": "Kendy"},
                {"date": "2015-05-19", "gender": "female", "age": 41, "name": "Maasai"},
                {"date": "2015-05-19", "gender": "male", "age": 21, "name": "Tom"}
        ]

Retrieving Data using limit operators
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Returns the data to the requesting user based on 'start'
and/or 'limit' query parameters. Use the start parameter to skip a number
of records and the limit parameter to limit the number of records returned.

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data?<code>start</code>=<code>start_value</code>
    </pre>

::

    curl -X GET 'https://ona.io/api/v1/dataviews/2/data?start=5'

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data?<code>start</code>=<code>start_value </code>&</code><code>limit</code>=<code>limit_value</code>
  </pre>

::

	curl -X GET 'https://ona.io/api/v1/dataviews/2/data?limit=2'

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data?<code>start</code>=<code>start_value</code>&</code><code>limit</code>=<code>limit_value</code>
  </pre>

::

	 curl -X GET 'https://ona.io/api/v1/dataviews/2/data?start=3&limit=4'


Counting the Data in the DataView
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data?<code>count</code>=<code>true</code>
    </pre>

::

    curl -X GET 'https://ona.io/api/v1/dataviews/2/data?count=true'


Example Response
----------------

::

    [
        {"count":36}
    ]


Export Dataview Data Asynchronously
-----------------------------------

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews/<code>{pk}</code>/export_async
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/dataviews/28058/export_async?format=xls

Response
^^^^^^^^
::

       HTTP 202 Accepted
       {"job_uuid": "d1559e9e-5bab-480d-9804-e32111e8b2b8"}


Check progress of exporting form data asynchronously
-----------------------------------------------------
.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews/<code>{pk}</code>/export_async?job_uuid=UUID
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/dataviews/28058/export_async?job_uuid=d1559e9e-5bab-480d-9804-e32111e8b2b8

Response
^^^^^^^^
If the job is done:

::

       HTTP 202 Accepted
       {
           "job_status": "SUCCESS",
           "export_url": "https://ona.io/api/v1/dataviews/28058/data.xls"
       }

Export Dataview Data Synchronously
-----------------------------------

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews/<code>{pk}</code>/data.{format}
	</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/dataviews/28058/data.xls

Response
^^^^^^^^

File is downloaded

Get a list of chart field endpoints for a specific dataview.
-------------------------------------------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/dataviews/<code>{dataview_pk}</code>/charts</pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/dataviews/4240/charts

Response
^^^^^^^^^

::

            {
                "id": 4240,
                "url": "https://ona.io/api/v1/dataviews/4240",
                "fields": {
                    "uuid": "https://ona.io/api/v1/dataviews/4240/charts?field_name=age",
                    "num": "https://ona.io/api/v1/dataviews/4240/charts?field_name=gender",
                    ...
                }
            }

Get a chart for a specific field in a dataview
----------------------------------------------

- ``field_name`` - a field name in the dataview
- ``format`` - ``json``

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/dataviews/<code>{dataview_id}</code>/charts.<code>{format}</code>?field_name=<code>field_name</code></pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/dataviews/4240/charts.json?field_name=age

Response
^^^^^^^^

 - ``html`` format response is a html, javascript and css to the chart
 - ``json`` format response is the ``JSON`` data that can be passed to a charting library
