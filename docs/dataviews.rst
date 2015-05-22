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

- ``col`` - The column the filter will be applied to.
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
            'query': '[{"col":"age", "filter":">", "value":"20"}]'
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
                    col: "age",
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
                    col: "age",
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
                    col: "age",
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
                    col: "age",
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
                    col: "age",
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
                    col: "age",
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
