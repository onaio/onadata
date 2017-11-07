Data
****

This endpoint provides access to submitted data in JSON format. Where:

- ``pk`` - the form unique identifier
- ``dataid`` - submission data unique identifier
- ``owner`` - username of the owner(user/organization) of the data point


GET JSON List of data end points
--------------------------------

Lists the data endpoints accessible to requesting user, for anonymous access

a list of public data endpoints is returned.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data
  </pre>

Example
^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data


Response
^^^^^^^^^
::

    [
        {
            "id": 4240,
            "id_string": "dhis2form",
            "title": "dhis2form",
            "description": "dhis2form",
            "url": "https://api.ona.io/api/v1/data/4240"
        },
        ...
    ]

GET JSON List of data end points using limit operators
-------------------------------------------------------

Lists the data endpoints accesible to the requesting user based on 'start'
and/or 'limit' query parameters. Use the start parameter to skip a number
of records and the limit parameter to limit the number of records returned.

.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/data/<code>{pk}</code>?<code>start</code>=<code>start_value</code>
    </pre>

::

    curl -X GET 'https://api.ona.io/api/v1/data/2?start=5'

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>?<code>start</code>=<code>start_value </code>&</code><code>limit</code>=<code>limit_value</code>
  </pre>

::

	curl -X GET 'https://api.ona.io/api/v1/data/2?limit=2'

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>?<code>start</code>=<code>start_value</code>&</code><code>limit</code>=<code>limit_value</code>
  </pre>

::

	 curl -X GET 'https://api.ona.io/api/v1/data/2?start=3&limit=4'

Download data in `csv` format
-----------------------------
.. raw:: html


  <pre class="prettyprint">
  <b>GET</b> /api/v1/data.csv</pre>

::

	curl -O https://api.ona.io/api/v1/data.csv

GET JSON List of data end points filter by owner
------------------------------------------------

Lists the data endpoints accessible to requesting user, for the specified
``owner`` as a query parameter.

.. raw:: html


  <pre class="prettyprint">
  <b>GET</b> /api/v1/data?<code>owner</code>=<code>owner_username</code>
  </pre>

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data?owner=ona

Get Submitted data for a specific form
------------------------------------------
Provides a list of json submitted data for a specific form.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code></pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/22845

Response
^^^^^^^^^
::

       [
            {
                "_id": 4503,
                "_bamboo_dataset_id": "",
                "_deleted_at": null,
                "_edited": false,
                "expense_type": "service",
                "_xform_id": 22845,
                "_xform_id_string": "exp",
                "_geolocation": [
                    null,
                    null
                ],
                "end": "2013-01-03T10:26:25.674+03",
                "start": "2013-01-03T10:25:17.409+03",
                "_duration": "",
                "expense_date": "2011-12-23",
                "_status": "submitted_via_web",
                "today": "2013-01-03",
                "_uuid": "2e599f6fe0de42d3a1417fb7d821c859",
                "imei": "351746052013466",
                "formhub/uuid": "46ea15e2b8134624a47e2c4b77eef0d4",
                "kind": "monthly",
                "_submission_time": "2013-01-03T02:27:19",
                "_submitted_by": "onaio",
                "required": "yes",
                "_attachments": [],
                "_tags": [],
                "_notes": [],
                "item": "Rent",
                "amount": "35000.0",
                "deviceid": "351746052013466",
                "subscriberid": "639027...60317",
                "_version": "1",
                "_media_count": 0,
                "_total_media": 0,
                "_media_all_received": true
            },
            ....
        ]

Get FLOIP flow results for a specific form
------------------------------------------
Provides a list of rows of submitted data for a specific form. Each row contains 6 values as specified |FLOIPSubmissionAPI|. The data is accessed from the data endpoint by specifiying the header ``Accept: "application/vnd.org.flowinterop.results+json"``.

.. |FLOIPSubmissionAPI| raw:: html

    <a href="https://github.com/FLOIP/flow-results/blob/master/specification.md#resource-data-found-at-external-path"
    target="_blank">here</a>

The values in each row are:
    - ``Timestamp`` - form submission timestamp
    - ``Row ID`` - Submission id
    - ``Contact ID`` - Name of the person who made the submission or null if unavailable
    - ``Question ID`` - The question field name
    - ``Response`` - The question response
    - ``Response metadata`` - The question options or null if none

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code> -H "Accept:application/vnd.org.flowinterop.results+json"</pre>

Example
^^^^^^^^^
::

    curl -X GET http://localhost:8000/api/v1/data/3 -H "Accept: application/vnd.org.flowinterop.results+json" -u username:password

Response
^^^^^^^^^
::

      [
          [ "2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male","female"]} ],
          [ "2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]
      ]

Get FLOIP flow results for a specific submission
------------------------------------------
Provides a list of rows of submitted data for a specific submission in a form in FLOIP resource data format as specified |FLOIPResourceData|.

.. |FLOIPResourceData| raw:: html

    <a href="https://github.com/FLOIP/flow-results/blob/master/specification.md#resource-data-found-at-external-path"
    target="_blank">here</a>

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code> -H "Accept: application/vnd.org.flowinterop.results+json"</pre>

Example
^^^^^^^^^
::

    curl -X GET http://localhost:8000/api/v1/data/210902/19158892 -H "Accept: application/vnd.org.flowinterop.results+json" -u username:password

Response
^^^^^^^^^
::

      [
          [ "2017-05-23T13:35:37.119-04:00", 20394823948, 923842093, "ae54d3", "female", {"option_order": ["male","female"]} ],
          [ "2017-05-23T13:35:47.822-04:00", 20394823950, 923842093, "ae54d7", "chocolate", null ]
      ]


Paginate data of a specific form
-------------------------------------------
Returns a list of json submitted data for a specific form using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

Example
^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/328.json?page=1&page_size=4


Sort submitted data of a specific form using existing fields
-------------------------------------------------------------
Provides a sorted list of json submitted data for a specific form by specifing the order in which the query returns matching data. Use the `sort` parameter to filter the list of submissions.The sort parameter has field and value pairs.

::

    {"field":value}

Query sorted by the age field ascending.

::

    {"age":1}

Descending sort query using the age field:

::

    {"age":-1}


Example of Ascending Sort
^^^^^^^^^^^^^^^^^^^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/data/328.json?sort={"age":1}

Example of Descending sort
^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

      curl -X GET https://api.ona.io/api/v1/data/328.json?sort={"age":-1}


Get a single data submission for a given form
---------------------------------------------

Get a single specific submission json data providing ``pk``

and ``dataid`` as url path parameters, where:

- ``pk`` - is the identifying number for a specific form
- ``dataid`` - is the unique id of the data, the value of ``_id`` or ``_uuid``

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code></pre>

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data/22845/4503

Response
^^^^^^^^^
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

Get the history of edits made to a submission
----------------------------------------------

Get a single specific submission json data providing ``pk``

and ``dataid`` as url path parameters, where:

- ``pk`` - is the identifying number for a specific form
- ``dataid`` - is the unique id of the data, the value of ``_id`` or ``_uuid``

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/history</pre>

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data/22845/4503/history

Response
^^^^^^^^^
::

    [
        {
            "_id": 3,
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
            "_attachments": [],
            "_notes": [],
            "item": "Rent",
            "amount": "35000.0",
            "deviceid": "351746052013466",
            "subscriberid": "639027...60317"
        },
        ....
    ]


Query submitted data of a specific form
----------------------------------------
Use the `query` or `data` parameter to pass in a JSON key/value query.

Example I
^^^^^^^
Query submissions where name is `tom`

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"name":"tom"}

Example II
^^^^^^^
Query submissions where age is greater than 21

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"age":{"$gt":"21"}}

Example III
^^^^^^^
Query submissions where age is less than or equal to 21

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"age":{"$lte":"21"}}

Example IV
^^^^^^^
Query submissions with case insensitive and partial search

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"name":{"$i":"hosee"}}


All Filters Options

========  ===================================
Filter    Description
========  ===================================
**$gt**   Greater than
**$gte**  Greater than or Equal to
**$lt**   Less than
**$lte**  Less or Equal to
**$i**    Case insensitive or partial search
========  ===================================

Query submitted data of a specific form using date_created
----------------------------------------------------------

Filter submissions using the date_created field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?date_created__year=2017


All Filters Options

=============================     ===================================
Filter                            Description
=============================     ===================================
**date_created__year**            Exact year e.g. 2017
**date_created__year__lt**        Year Less than
**date_created__year__lte**       Year Less than or Equal to
**date_created__year__gt**        Year Greater than
**date_created__year__gte**       Year Greater than or Equal to
**date_created__month**           Exact month e.g. 11
**date_created__month__lt**       Month Less than
**date_created__month__lte**      Month Less than or Equal to
**date_created__month__gt**       Month Greater than
**date_created__month__gte**      Month Greater than or Equal to
**date_created__day**             Exact day e.g. 13
**date_created__day__lt**         Day Less than
**date_created__day__lte**        Day Less than or Equal to
**date_created__day__gt**         Day Greater than
**date_created__day__gte**        Day Greater than or Equal to
=============================     ===================================

Filter options can be chained to narrow results even further.


Query submitted data of a specific form using date_modified
-----------------------------------------------------------

Filter submissions using the date_modified field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?date_modified__month=11

All Filters Options

=============================     ===================================
Filter                            Description
=============================     ===================================
**date_modified__year**           Exact year e.g. 2017
**date_modified__year__lt**       Year Less than
**date_modified__year__lte**      Year Less than or Equal to
**date_modified__year__gt**       Year Greater than
**date_modified__year__gte**      Year Greater than or Equal to
**date_modified__month**          Exact month e.g. 11
**date_modified__month__lt**      Month Less than
**date_modified__month__lte**     Month Less than or Equal to
**date_modified__month__gt**      Month Greater than
**date_modified__month__gte**     Month Greater than or Equal to
**date_modified__day**            Exact day e.g. 13
**date_modified__day__lt**        Day Less than
**date_modified__day__lte**       Day Less than or Equal to
**date_modified__day__gt**        Day Greater than
**date_modified__day__gte**       Day Greater than or Equal to
=============================     ===================================

Filter options can be chained to narrow results even further.


Query submitted data of a specific form using last_edited
---------------------------------------------------------

Filter submissions using the last_edited field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?last_edited__year=2017&last_edited__month=2

All Filters Options

=============================     ===================================
Filter                            Description
=============================     ===================================
**last_edited__year**             Exact year e.g. 2017
**last_edited__year__lt**         Year Less than
**last_edited__year__lte**        Year Less than or Equal to
**last_edited__year__gt**         Year Greater than
**last_edited__year__gte**        Year Greater than or Equal to
**last_edited__month**            Exact month e.g. 11
**last_edited__month__lt**        Month Less than
**last_edited__month__lte**       Month Less than or Equal to
**last_edited__month__gt**        Month Greater than
**last_edited__month__gte**       Month Greater than or Equal to
**last_edited__day**              Exact day e.g. 13
**last_edited__day__lt**          Day Less than
**last_edited__day__lte**         Day Less than or Equal to
**last_edited__day__gt**          Day Greater than
**last_edited__day__gte**         Day Greater than or Equal to
=============================     ===================================

Filter options can be chained to narrow results even further.


Query submitted data of a specific form using version
-----------------------------------------------------

Filter submissions using the version field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?version=2324243


Query submitted data of a specific form using status
----------------------------------------------------

Filter submissions using the status field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?status=submitted_via_web


Query submitted data of a specific form using uuid
--------------------------------------------------

Filter submissions using the uuid field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?uuid=9c6f3468-cfda-46e8-84c1-75458e72805d


Query submitted data of a specific form using user
--------------------------------------------------

Filter submissions using the user field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?user__id=260

All Filters Options

===================     ===================================
Filter                  Description
===================     ===================================
**user__id**            user's id
**user__username**      user's username
===================     ===================================


Query submitted data of a specific form using submitted_by
----------------------------------------------------------

Filter submissions using the submitted_by field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?submitted_by__username=hunter2

All Filters Options

===========================     ===================================
Filter                          Description
===========================     ===================================
**submitted_by__id**            submitted_by user's id
**submitted_by__username**      submitted_by user's username
===========================     ===================================


Query submitted data of a specific form using survey_type
---------------------------------------------------------

Filter submissions using the survey_type field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?survey_type__slug=fortytwo


Query submitted data of a specific form using media_all_received
----------------------------------------------------------------

Filter submissions using the media_all_received field

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/22845?media_all_received=true


Query submitted data of a specific form using Tags
--------------------------------------------------
Provides a list of json submitted data for a specific data/form matching specific
tags. Use the `tags` query parameter to filter the list of forms, `tags`
should be a comma separated list of tags.

You can use the `not_tagged` query parameter to exclude data/forms that is not tagged
with the specific comma separated list of tags.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data?<code>tags</code>=<code>tag1,tag2</code></pre>
  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>?<code>tags</code>=<code>tag1,tag2</code></pre>
  <pre class="prettyprint">
  <b>GET</b> /api/v1/data?<code>not_tagged</code>=<code>tag1,tag2</code></pre>
  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>?<code>not_tagged</code>=<code>tag2</code></pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/22845?tags=monthly

Tag a submission data point
----------------------------

A ``POST`` payload of parameter `tags` with a comma separated list of tags.

Examples
^^^^^^^^^
- ``animal fruit denim`` - space delimited, no commas
- ``animal, fruit denim`` - comma delimited

.. raw:: html

  <pre class="prettyprint">
  <b>POST</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/labels</pre>

**Payload**
::

    {"tags": "tag1, tag2"}

Delete a specific tag from a submission
----------------------------------------

.. raw:: html

  <pre class="prettyprint">
  <b>DELETE</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/labels/<code>tag_name</code></pre>

Request
^^^^^^^^^
::

    curl -X DELETE https://api.ona.io/api/v1/data/28058/20/labels/tag1

or to delete the tag "hello world"

::

    curl -X DELETE https://api.ona.io/api/v1/data/28058/20/labels/hello%20world

Response
^^^^^^^^^
::

	HTTP 200 OK

Get list of public data endpoints
----------------------------------

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/public
  </pre>

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data/public

Response
^^^^^^^^^
::

    [
        {
            "id": 4240,
            "id_string": "dhis2form",
            "title": "dhis2form",
            "description": "dhis2form",
            "url": "https://api.ona.io/api/v1/data/4240"
        },
        ...
    ]

Get enketo edit link for a submission instance
-----------------------------------------------
.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>/enketo
  </pre>

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/28058/20/enketo?return_url=url

Response
^^^^^^^^^
::

    {"url": "https://hmh2a.enketo.formhub.org"}

Delete a specific submission instance
--------------------------------------

**Delete a specific submission in a form**

.. raw:: html

  <pre class="prettyprint">
  <b>DELETE</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>
  </pre>

Example
^^^^^^^^^
::

    curl -X DELETE https://api.ona.io/api/v1/data/28058/20

Response
^^^^^^^^^
::

    HTTP 204 No Content


GEOJSON
-------

Get a valid geojson value from the submissions

**Options**

- ``geo_field`` - valid field that can be converted to a geojson (Point, LineString, Polygon).
- ``fields`` - additional comma separated values that are to be added to the properties section

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson
  </pre>

**With options**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson?geo_field=<code>{field_name}</code>&fields=<code>{list,of,fields}</code>
  </pre>

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/28058/20.geojson

Response
^^^^^^^^^
::

    HTTP 200 OK

Response
^^^^^^^^^
::

    {
        "type": "Feature",
        "geometry": {
            "type": "GeometryCollection",
            "geometries": [{
                "type": "Point",
                "coordinates": [36.787219, -1.294197]
            }]
        },
        "properties": {
            "id": 6448,
            "xform": 65
        }
    }


**List the geojson values**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>.geojson
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/28058.geojson

Response
^^^^^^^^^

    **HTTP 200 OK**

Response
^^^^^^^^^
::

    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "GeometryCollection",
                    "geometries": [{
                        "type": "Point",
                        "coordinates": [36.787219, -1.294197]
                    }]
                },
                    "properties": {
                        "id": 6448,
                        "xform": 65
                    }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "GeometryCollection",
                    "geometries": [{
                        "type": "Point",
                        "coordinates": [36.7872606, -1.2942131]
                    }]
                },
                "properties": {
                    "id": 6447,
                    "xform": 65
                }
            }]
    }

OSM
----

The `.osm` file format concatenates all the files for a form or individual submission. When the `.json` endpoint is accessed, the individual osm files are listed on the `_attachments` key.

OSM endpoint for all osm files uploaded to a form concatenated.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>.osm
  </pre>

Example
^^^^^^^^^
::

	curl -X GET https://api.ona.io/api/v1/data/28058.osm

OSM endpoint with all osm files for a specific submission concatenated.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{data_id}</code>.osm
  </pre>

Example
^^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/data/28058/20.osm
