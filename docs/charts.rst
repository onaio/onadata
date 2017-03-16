Charts
*********

View chart for specific fields in a form or dataset.

List of chart chart endpoints accessible to registered user
-----------------------------------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts</pre>

Example
^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/charts

Response
^^^^^^^^^
::

        [{
            "id": 4240,
            "id_string": "dhis2form",
            "url": "https://api.ona.io/api/v1/charts/4240",
        }
        ...

Get a list of chart field endpoints for a specific form or dataset.
-------------------------------------------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts/<code>{formid}</code></pre>

Example
^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/charts/4240

Response
^^^^^^^^^

::

            {
                "id": 4240,
                "id_string": "dhis2form",
                "url": "https://api.ona.io/api/v1/charts/4240",
                "fields": {
                    "uuid": "https://api.ona.io/api/v1/charts/4240?field_name=uuid",
                    "num": "https://api.ona.io/api/v1/charts/4240?field_name=num",
                    ...
                }
            }

Get a chart for a specific field in a form
--------------------------------------------

- ``field_name`` - a field name in the form
- ``format`` - can be ``html`` or ``json``

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts/<code>{formid}</code>.<code>{format}</code>?field_name=<code>field_name</code></pre>

Example
^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/charts/4240.html?field_name=age

Response
^^^^^^^^

 - ``html`` format response is a html, javascript and css to the chart
 - ``json`` format response is the ``JSON`` data that can be passed to a charting library

Get a chart for field grouped by another field in the form
----------------------------------------------------------

- ``field_name`` - a field name in the form, for group by multiple fields
  requires this to be a numeric field.
- ``group_by`` - a field name in the form to group by, if it is a comma
  separated field list then the field_name will be grouped by all the fields in
  the list.
- ``format`` - can be ``html`` or ``json``

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts/<code>{formid}</code>.<code>{format}</code>?field_name=<code>field_name</code>&group_by=<code>field1,field2</code></pre>

Example
^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/charts/4240.json?field_name=age&group_by=year
    curl -X GET https://api.ona.io/api/v1/charts/4240.json?field_name=age&group_by=sex,year

Response
^^^^^^^^

 - ``html`` format response is a html, javascript and css to the chart
 - ``json`` format response is the ``JSON`` data that can be passed to a charting library

 .. raw:: json

    {
    "field_type": "integer",
    "data_type": "numeric",
    "field_xpath": "age",
    "data": [
        {
        "mean": 45.0,
        "sum": 855.0,
        "year": "1880",
        "sex": [
            "Female"
        ]
        },
        {
        "mean": 45.0,
        "sum": 855.0,
        "year": "1850",
        "sex": [
            "Female"
        ]
        },
    "field_label": "Age",
    "field_name": "age",
    "xform": 4240
    }

Get a chart data for all fields in a form
------------------------------------------

The only field ommitted is instanceID since it is unique for every record.

- ``fields`` - is a comma separated list of fields to be included in the response. If ``fields=all`` then all the fields of the form  will be returned.

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts/<code>{formid}</code>?<code>fields=all</code>
    </pre>

Example
^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/charts/4240?fields=all

Response
^^^^^^^^^

 - `json` format response is the `JSON` data for each field that can be passed to a charting library


