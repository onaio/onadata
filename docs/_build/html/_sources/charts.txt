Charts
*********

Charts List
=============

View chart for specific fields in a form or dataset.

List of chart chart endpoints accessible to registered user
-----------------------------------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts</pre>

Example
^^^^^^^^
::

       curl -X GET https://ona.io/api/v1/charts

Response
^^^^^^^^^
::

        [{

            "id": 4240,
            "id_string": "dhis2form"
            "url": "https://ona.io/api/v1/charts/4240",
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

    curl -X GET https://ona.io/api/v1/charts/4240

Response
^^^^^^^^^

::

            {


                "id": 4240,

                "id_string": "dhis2form"

                "url": "https://ona.io/api/v1/charts/4240",

                "fields": {

                "uuid": "https://ona.io/api/v1/charts/4240?field_name=uuid",

                "num": "https://ona.io/api/v1/charts/4240?field_name=num",

                    ...

                }

            }

Get a chart for a specific field in a form
--------------------------------------------

- ``field_name`` - a field name in the form
- ``format`` - can be ``html`` or ``json``

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/charts/<code>{formid}</code>.<code>{format}</code>?\
    field_name=<code>field_name</code></pre>

Example
^^^^^^^
::

    curl -X GET https://ona.io/api/v1/charts/4240.html?field_name=age

Response
^^^^^^^^

 - ``html`` format response is a html, javascript and css to the chart
 - ``json`` format response is the ``JSON`` data that can be passed to a charting
    library

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

       curl -X GET https://ona.io/api/v1/charts/4240?fields=all

Response
^^^^^^^^^

 - `json` format response is the `JSON` data for each field that can be
    passed to a charting library

    