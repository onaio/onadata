DataView
********

This endpoint provides access to filtered data from submitted XForm data.

Where:

- ``pk`` - is the dataview id


Create a new DataView
---------------------

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/dataviews</pre>

Example
^^^^^^^
::

        {
            'name': "My DataView",
            'xform': 'https://ona.io/api/v1/forms/12',
            'project':  'https://ona.io/api/v1/projects/13',
            'columns': '["name", "age", "gender"]',
            'query': '[{"col":"age", "filter":">", "value":"20"}]'
        }

Response
^^^^^^^^

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
---------------------

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews/<code>{pk}</code></pre>

Response
^^^^^^^^

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
---------------------

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/dataviews</pre>

Response
^^^^^^^^

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
-----------------

.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/dataviews/<code>{pk}</code></pre>

Example
^^^^^^^
::

        {
            'name': "My DataView updated",
            'xform': 'https://ona.io/api/v1/forms/12',
            'project':  'https://ona.io/api/v1/projects/13',
            'columns': '["name", "age", "gender"]',
            'query': '[{"col":"age", "filter":">", "value":"30"}]'
        }

Response
^^^^^^^^

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
-----------------

.. raw:: html

	<pre class="prettyprint">
	<b>PATCH</b> /api/v1/dataviews/<code>{pk}</code></pre>

Example
^^^^^^^
::

        {
            'columns': '["name", "age", "gender", "date"]'
        }

Response
^^^^^^^^

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
-----------------

.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/dataviews/<code>{pk}</code></pre>

Response
^^^^^^^^

::

    HTTP 204 NO CONTENT


