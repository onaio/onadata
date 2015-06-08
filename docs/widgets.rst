Widgets
********

This endpoint provides ability to persist charts.

Where:

- ``pk`` - is the widget id
- ``formid`` - is the xform/dataview id

Definition
^^^^^^^^^^
- ``title`` - Title of the widget
- ``content_object`` - Data source of the widget. XForm/Dataview
- ``description`` Widget description
- ``widget_type`` The Widget type
- ``view_type``- Stores information to help the widget display the data
- ``column`` - The column of the data being charted
- ``group_by`` - This is another column (not equal to column) that the data should be grouped by
- ``key`` - Unique identifier

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
            "content_object": "https://ona.io/api/v1/forms/9929",
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age"
        }

Response
--------

::

        {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
              "data": []
        }



Retrieve a Widget
^^^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code></pre>

Response
--------

::

       {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
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
              "key": "3e87d40427914e56840fc0c5f17401c6",
              "title": "Tomorrow never comes",
              "description": "Movies",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": age,
              "content_object": "https://ona.io/api/v1/forms/9929",
              "data": []
        },
        {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
              "data": []
        }
    ]


Update a Widget
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PUT</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code></pre>

Example
-------
::

        {
            "title": "My new title updated",
            "description": "new description",
            "content_object": "https://ona.io/api/v1/forms/9929",
            "widget_type": "charts",
            "view_type": "horizontal-bar",
            "column": "age"
        }

Response
--------

::

        {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
              "data": []
        }

Patch a Widget
^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>PATCH</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code></pre>

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
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "gender",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
              "data": []
        }

Delete a Widget
^^^^^^^^^^^^^^^^^

.. raw:: html

	<pre class="prettyprint">
	<b>DELETE</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code></pre>

Response
--------

::

    HTTP 204 NO CONTENT



Widget Data
^^^^^^^^^^^
To get the widgets data, set the data flag to true.

.. raw:: html

	<pre class="prettyprint">
	<b>GET</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code>?data=<code>true</code></pre>

Response
--------

::

       {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
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
	<b>GET</b> /api/v1/widgets/<code>{formid}</code>/<code>{pk}</code>?key=<code>{valid widget key}</code></pre>

Response
--------

::

       {
              "key": "e60c148d19464365b4e9a5d88f52694b",
              "title": "My new title updated",
              "description": "new description",
              "widget_type": "charts",
              "view_type": "horizontal-bar",
              "column": "age",
              "group_by": null,
              "content_object": "https://ona.io/api/v1/forms/9929",
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

