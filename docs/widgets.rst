Widgets
********

This endpoint provides ability to persist charts.

Where:

- ``pk`` - is the widget id

Definition
^^^^^^^^^^
- ``id`` - The ID of the widget
- ``title`` - Title of the widget
- ``content_object`` - Data source of the widget. XForm/Dataview
- ``description`` Widget description
- ``aggregation`` Description of an aggregation used during a group_by
- ``order`` The order of the widget. The order will be made unique to the XForm/Dataview by linearly reordering
- ``widget_type`` The Widget type
- ``view_type``- Stores information to help the widget display the data
- ``column`` - The column of the data being charted
- ``group_by`` - This is another column (not equal to column) that the data should be grouped by
- ``key`` - Unique identifier
- ``metadata`` - json dict to store extra information.

Create a new Widget
^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>POST</b> /api/v1/widgets</pre>

Example
-------
::

        {
            "title": "My new title",
            "description": "new description",
            "aggregation": "mean",
            "order": 0,
            "content_object": "https://api.ona.io/api/v1/forms/9929",
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age"
        }

Response
--------

::

        {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        }



Retrieve a Widget
^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets/<code>{pk}</code></pre>

Response
--------

::

       {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        }

List all Widgets
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets</pre>

Response
--------

::


    [
        {
              "id": 1,
              "key": "3e87d40427914e56840fc0c5f17401c6",
              "title": "Tomorrow never comes",
              "description": "Movies",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": age,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        },
        {
              "id": 2,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        }
    ]


Update a Widget
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/widgets/<code>{pk}</code></pre>

Example
-------
::

        {
            "title": "My new title updated",
            "description": "new description",
            "aggregation": "mean",
            "order": 0,
            "content_object": "https://api.ona.io/api/v1/forms/9929",
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age"
        }

Response
--------

::

        {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        }

Patch a Widget
^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PATCH</b> /api/v1/widgets/<code>{pk}</code></pre>

Example
-------
::

        {
            'column': 'gender'
        }

Response
--------

::

         {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": []
        }

Delete a Widget
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/widgets/<code>{pk}</code></pre>

Response
--------

::

    HTTP 204 NO CONTENT



Widget Data
^^^^^^^^^^^
To get the widgets data, set the data flag to true.

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets/<code>{pk}</code>?data=<code>true</code></pre>

Response
--------

::

       {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": [
                    {
                      "count": 2,
                      "age": "21"
                    },
                    {
                      "count": 3,
                      "age": "22"
                    },
                    {
                      "count": 1,
                      "age": "23"
                    },
               ]
        }


Widget Data With Valid Key
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets?key=<code>{valid widget key}</code></pre>

Response
--------

::

       {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": [
                    {
                      "count": 2,
                      "age": "21"
                    },
                    {
                      "count": 3,
                      "age": "22"
                    },
                    {
                      "count": 1,
                      "age": "23"
                    },
               ]
        }

Filter Widget Using FormID
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets?xform=<code>{form id}</code></pre>

Response
--------

::

       {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/forms/9929",
              "data": [
                    {
                      "count": 2,
                      "age": "21"
                    },
                    {
                      "count": 3,
                      "age": "22"
                    },
                    {
                      "count": 1,
                      "age": "23"
                    },
               ]
        }

Filter Widget Using DataView ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets?dataview=<code>{dataview id}</code></pre>

Response
--------

::

       {
              "id": 1,
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "aggregation": "mean",
              "order": 0,
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://api.ona.io/api/v1/dataviews/12",
              "data": [
                    {
                      "count": 2,
                      "age": "21"
                    },
                    {
                      "count": 3,
                      "age": "22"
                    },
                    {
                      "count": 1,
                      "age": "23"
                    },
               ]
        }
