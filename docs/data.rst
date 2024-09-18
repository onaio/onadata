Data
****

This endpoint provides access to submitted data in JSON format. Where:

- ``pk`` - the form unique identifier
- ``dataid`` - submission data unique identifier
- ``owner`` - username of the owner(user/organization) of the data point


GET JSON List of data end points
--------------------------------

Lists the data endpoints accessible to requesting user, for anonymous access a list of public data endpoints is returned.

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

Fetch XForm ODK data for all forms per account in `csv` format
--------------------------------------------------------------
Pull all form data for forms located within your account

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data.csv

Response
^^^^^^^^^
::
    description,id,id_string,title,url
     ,549,form1,First Form,https://stage-odk.ona.io/api/v1/data/549.csv
     ,569,form2,Second Form,https://stage-odk.ona.io/api/v1/data/569.csv
     ,570,Smallform,Smallform,https://stage-odk.ona.io/api/v1/data/570.csv

Stream XForm submission data in `csv` format
--------------------------------------------

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data/1343.csv

Response
^^^^^^^^^
::
    hello,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,2,n/a,uuid:6a477d27-343c-44c2-9204-bd42ec3e0796,77466,6a477d27-343c-44c2-9204-bd42ec3e0796,2021-02-23T14:14:47,2021-02-23T14:14:47,,,202001170844,,winny,0,0,True,1343
    Test que,14,14,40.446947 27.283625 0 0,40.446947,27.283625,0,0,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,n/a,2,n/a,uuid:a09a9b71-b98a-4904-ab04-1ed162ab2b02,186964,a09a9b71-b98a-4904-ab04-1ed162ab2b02,2021-05-27T12:38:14,2021-05-27T12:38:14,,,202001170844,,winny,0,0,True,1343

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

GET JSON list of submitted data for a specific form
---------------------------------------------------
Provides a JSON list of submitted data for a specific form.

Note: Responses are automatically paginated when requesting a list of data that surpasses 10,000 records.

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
                "_date_modified": "2013-01-03T02:29:20",
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

GET XML list of submitted data for a specific form
--------------------------------------------------

Provides an XML list of submitted data for a specific form.

..  raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/data/<code>{pk}</code>.xml
    </pre>

Example
^^^^^^^^
::

        curl -X GET https://api.ona.io/api/v1/data/574.xml

Response
^^^^^^^^^
::

        <submission-batch serverTime="2021-07-02T08:16:24.304534+00:00">
            <submission-item bambooDatasetId="" dateCreated="2021-07-02T08:16:24.091445+00:00" duration="" edited="False" formVersion="2014111" lastModified="2021-07-02T08:16:24.206278+00:00" mediaAllReceived="True" mediaCount="1" objectID="1957" reviewComment="" reviewStatus="" status="submitted_via_web" submissionTime="2021-07-02T08:16:24" submittedBy="bob" totalMedia="1">
                <data id="transportation_2011_07_25" version="2014111">
                    <transport>
                        <available_transportation_types_to_referral_facility>none</available_transportation_types_to_referral_facility>
                        <loop_over_transport_types_frequency>
                            <ambulance></ambulance>
                            <bicycle></bicycle>
                            <boat_canoe></boat_canoe>
                            <bus></bus>
                            <donkey_mule_cart></donkey_mule_cart>
                            <keke_pepe></keke_pepe>
                            <lorry></lorry>
                            <motorbike></motorbike>
                            <taxi></taxi>
                            <other></other>
                        </loop_over_transport_types_frequency>
                    </transport>
                    <image1 type="file">1335783522563.jpg</image1>
                    <meta>
                        <instanceID>uuid:5b2cc313-fc09-437e-8149-fcd32f695d41</instanceID>
                    </meta>
                </data>
                <linked-resources>
                    <attachments>
                        <id>50</id>
                        <name>1335783522563.jpg</name>
                        <xform>574</xform>
                        <filename>bob/attachments/574_transportation_2011_07_25/1335783522563.jpg</filename>
                        <instance>1957</instance>
                        <mimetype>image/jpeg</mimetype>
                        <download_url>/api/v1/files/50?filename=bob/attachments/574_transportation_2011_07_25/1335783522563.jpg</download_url>
                        <small_download_url>/api/v1/files/50?filename=bob/attachments/574_transportation_2011_07_25/1335783522563.jpg&amp;suffix=small</small_download_url>
                        <medium_download_url>/api/v1/files/50?filename=bob/attachments/574_transportation_2011_07_25/1335783522563.jpg&amp;suffix=medium</medium_download_url>
                    </attachments>
                </linked-resources>
            </submission-item>
            <submission-item>
                ...
            </submission-item>
        </submission-batch>

Get FLOIP flow results for a specific form
------------------------------------------
Provides a list of rows of submitted data for a specific form. Each row contains 6 values as specified |FLOIPSubmissionAPI|. The data is accessed from the data endpoint by specifying the header ``Accept: "application/vnd.org.flowinterop.results+json"``.

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
------------------------------------------------
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
---------------------------------
Returns a list of JSON or XML submitted data for a specific form using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page.

There are a few important facts to note about retrieving paginated data:

1. The maximum number of items that can be requested in a page via the ``page_size`` query param is 10,000
2. Information regrading transversal of the paginated responses can be found in `the Link header <https://tools.ietf.org/html/rfc5988>`_ returned in the response. *Note: Some relational links may not be present depending on the page accessed i.e the ``first`` relational page link won't be present on the first page response*

JSON Example
^^^^^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/328.json?page=1&page_size=4

Sample response with link header
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

      curl -i "localhost:8000/api/v1/data/2?page=1&page_size=1"

**Response Header:** ::

      ...
      Link: <http://localhost:8000/api/v1/data/2?page=2&page_size=1>; rel="next", <http://localhost:8000/api/v1/data/2?page=3&page_size=1>; rel="last"

**JSON Response:** ::

      [
        {
            "_id":1,"_tags":[],"_uuid":"78afb566-8293-4f42-a83f-99d5ba0061e2",
            "_notes":[]"_edited":false,"_status":"submitted_via_web",
            "_version":"202010260841","_duration":"","_xform_id":2,
            "plot_count":"1","_attachments":[],"_geolocation":[null,null],
            "_media_count":0,"_total_media":0,"formhub/uuid":"281845ab2d214ff6ac08526c0484fe34",
            "_submitted_by":null,"meta/instanceID":"uuid:78afb566-8293-4f42-a83f-99d5ba0061e2",
            "_submission_time":"2020-10-26T08:49:06","_xform_id_string":"nested_repea",
            "_bamboo_dataset_id":"","_media_all_received":true
        }
      ]


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

Fetch data on select columns for a given form
---------------------------------------------------

Returns a list of the selected columns from the submitted data. Use the ``fields`` parameter to specify the column data that should be returned.

- ``fields`` - a comma separated list of columns on the given form.


.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{form_pk}</code>.json?fields=<code>["field1", "field2"]</code>
  </pre>

Example
^^^^^^^^^
::

       curl -X GET https://api.ona.io/api/v1/data/513322.json?fields=["_id", "_last_edited"]

Response
^^^^^^^^^
::

    [
        {
            "_id": 64999942,
            "_last_edited": null
        },
        {
            "_id": 64999819,
            "_last_edited": null
        },
        {
            "_id": 64999278,
            "_last_edited": null
        },
        {
            "_id": 64999082,
            "_last_edited": null
        },
        {
            "_id": 60549177,
            "_last_edited": null
        },
        {
            "_id": 60549136,
            "_last_edited": null
        }
    ]


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

ISO 8601 date formats are supported. Below are examples of common formats:

- ``YYYY-MM-DD`` (e.g., 2024-09-18)
- ``YYYY-MM-DDThh:mm:ss`` (e.g., 2024-09-18T14:30:00)
- ``YYYY-MM-DDThh:mm:ssZ`` (e.g., 2024-09-18T14:30:00Z)
- ``YYYY-MM-DDThh:mm:ss.ssssssZ`` (e.g., 2024-09-18T14:30:00.169615Z)
- ``YYYY-MM-DDThh:mm:ss±hh:mm`` (e.g., 2024-09-17T13:39:40+00:00)
- ``YYYY-MM-DDThh:mm:ss.ssssss±hh:mm`` (e.g., 2024-09-17T13:39:40.169615+00:00)

When quering a date time field whose value is in ISO format such as ``2020-12-18T09:36:19.767455+00:00``, it is important to ensure the ``+`` (plus) is encoded to ``%2b``.

``+`` without encoding is parsed as whitespace. So ``2020-12-18T09:36:19.767455+00:00`` should be converted to ``2020-12-18T09:36:19.767455%2b00:00``.


Example I
^^^^^^^^^
Query submissions where name is `tom`

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"name":"tom"}

Example II
^^^^^^^^^^
Query submissions where age is greater than 21

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"age":{"$gt":"21"}}

Example III
^^^^^^^^^^^
Query submissions where age is less than or equal to 21

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"age":{"$lte":"21"}}

Example IV
^^^^^^^^^^
Query submissions with case insensitive and partial search

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"name":{"$i":"hosee"}}

Example V
^^^^^^^^^^
Query submissions collected before specific date

::

    curl -X GET https://api.ona.io/api/v1/data/22845.json?query={"_submission_time":{"$lte": "2020-08-31"}}

Example VI
^^^^^^^^^^
Query submissions collected within specific dates

::

    curl -X GET https://api.ona.io/api/v1/data/22845.json?query={"_submission_time":{"$gte": "2020-01-01", "$lte": "2020-08-31"}}

Example VII
^^^^^^^^^^^
Query submissions where age is 21 or name is hosee

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"$or": [{"age": "21", "name": "hosee"}]}

Example VIII
^^^^^^^^^^^^
Query submissions with APPROVED submission review status

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"_review_status" : "1"}

Example IX
^^^^^^^^^^^^
Query submissions with REJECTED submission review status

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"_review_status" : "2"}

Example X
^^^^^^^^^^
Query submissions with PENDING submission review status

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"_review_status" : "3"}

Example XI
^^^^^^^^^^
Query submissions with pending submission review status or NULL

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"$or": [{"_review_status": "3"}, {"_review_status": null}]}

Example XII
^^^^^^^^^^^
Query submissions with `NULL` submission review status

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"_review_status": null}

Example XIII
^^^^^^^^^^^^

Query submissions collected within specific dates or edited within specific dates.

::

    curl -X GET https://api.ona.io/api/v1/data/22845?query={"$or": [{"_submission_time":{"$gte": "2020-01-01", "$lte": "2020-08-31"}}, {"_last_edited":{"$gte": "2020-01-01", "$lte": "2020-08-31"}}]}
    

All Filters Options

==================================================
Filter   Description
==================================================
**$gt**  Greater than
**$gte** Greater than or Equal to
**$lt**  Less than
**$lte** Less or Equal to
**$i**   Case insensitive or partial search
**$or**  Or
==================================================

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

Delete a subset of submissions
-------------------------------

**Delete multiple submissions in a form**

.. raw:: html

  <pre class="prettyprint">
  <b>DELETE</b> /api/v1/data/<code>{pk}</code>
  </pre>

A POST payload of parameter `instance_ids` with a comma separated list of submission ids.

**Payload**
::

    instance_ids = '101425,108428,1974624'

Example
^^^^^^^^^
::

    'curl -X DELETE https://api.ona.io/api/v1/data/28058' -d 'instance_ids=101425,108428,1974624'

Response
^^^^^^^^^
::

    {"status_code": 200, "message": "3 records were deleted"}

Delete all submissions in a form
---------------------------------

**Delete all submissions in a form**

.. raw:: html

  <pre class="prettyprint">
  <b>DELETE</b> /api/v1/data/<code>{pk}</code>
  </pre>

A POST payload of parameter `delete_all` with the value 'True'. The value is 'False' by default.

**Payload**
::

    delete_all = 'True'

Example
^^^^^^^^^
::

    'curl -X DELETE https://api.ona.io/api/v1/data/28058' -d 'delete_all="True"'

Response
^^^^^^^^^
::

    {"status_code": 200, "message": "3 records were deleted"}


Permanent Deletion of Submissions
------------------------------------

**Permanently Delete a specific submission instance**

`DELETE /api/v1/data/{pk}/{dataid}`

A POST payload of parameter `permanent_delete` with the value 'True'. The value is 'False' by default.

Note: This functionality is only enabled when the ``ENABLE_SUBMISSION_PERMANENT_DELETE`` setting is set to `True` within the application

**Payload**
::

    permanent_delete = 'True'

Example
^^^^^^^^^
::

    `curl -X DELETE https://api.ona.io/api/v1/data/28058' -d 'permanent_delete=True'`

Response
^^^^^^^^^

::
    HTTP 204 No Content

**Permanently Delete a subset of submissions**

`DELETE /api/v1/data/{pk}`

Example
^^^^^^^^^
::

    `curl -X DELETE https://api.ona.io/api/v1/data/28058' -d 'permanent_delete=True' -d 'instance_ids=101425,108428,1974624'`

Response
^^^^^^^^^

::

    {
        "status_code": "200",
        "message": "3 records were deleted"
    }


GEOJSON
-------

Get a valid geojson value from the submissions

**Options**

- ``geo_field`` - valid field that can be converted to a geojson (Point, LineString, Polygon).
- ``fields`` - additional comma separated values that are to be added to the properties section
- ``simple_style`` - boolean to enable or disable Mapbox Geojson simplestyle spec
- ``title`` - adds a title field and value to geojson properties section

**List all the geojson values for a submission**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{form_pk}</code>/<code>{dataid}</code>.geojson
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


**List all the geojson values for a given form**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{form_pk}</code>.geojson
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

**List the geojson data, for a polygon field, for a given submission**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson?geo_field=<code>{name_of_field_on_form}</code>
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/513322/60549136.geojson?geo_field=my_geoshape

Response
^^^^^^^^^

    **HTTP 200 OK**

Response
^^^^^^^^^
::

    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        36.747679,
                        -1.300717
                    ],
                    [
                        36.752386,
                        -1.305222
                    ],
                    [
                        36.751879,
                        -1.300642
                    ],
                    [
                        36.747679,
                        -1.300717
                    ]
                ]
            ]
        },
        "properties": {
            "id": 60549136,
            "xform": 513322
        }
    }

**List the geojson data, for a geotrace field, for a given submission. Add fields to the properties attribute**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson?geo_field=<code>{name_of_field_on_form}</code>
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/513322/60549136.geojson?geo_field=my_geotrace

Response
^^^^^^^^^

    **HTTP 200 OK**

Response
^^^^^^^^^
::

    {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [
                    36.745623,
                    -1.302819
                ],
                [
                    36.750326,
                    -1.299129
                ]
            ]
        },
        "properties": {
            "id": 60549136,
            "xform": 513322
        }
    }

**Fetch geojson values for a submission with populated properties attribute**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{pk}</code>/<code>{dataid}</code>.geojson?fields=<code>{_id,_last_edited}</code>
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/513322/60549136.geojson?fields=_id,_last_edited

Response
^^^^^^^^^

    **HTTP 200 OK**

Response
^^^^^^^^^
::

    {
        "type": "Feature",
        "geometry": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "type": "Point",
                    "coordinates": [
                        36.744421,
                        -1.29943
                    ]
                }
            ]
        },
        "properties": {
            "id": 60549136,
            "xform": 513322,
            "_id": 60549136,
            "_last_edited": null
        }
    }

**List all the geojson values for a given form with simplestyle-spec enabled and title prop set**

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{form_pk}</code>.geojson?geo_field=<code>{name_of_field_on_form}</code>&simple_style=true&title=<code>{name_of_title_field_on_form}</code>
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/28058.geojson?geo_field=my_geoshape&style_spec=true

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
                    "type": "Point",
                    "coordinates": [36.787219, -1.294197]
                },
                    "properties": {
                        "id": 6448,
                        "xform": 65,
                        "title": "my_field"
                    }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [36.7872606, -1.2942131]
                },
                "properties": {
                    "id": 6447,
                    "xform": 65,
                    "title": "my_field"
                }
            }]
    }

**Paginate geojson data for a given form**
Returns a list of geojson features for a specific form using page number and the number of items per page.
Use the ``page`` parameter to specify page number and ``page_size`` parameter to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of features that should be returned in a single page.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/data/<code>{form_pk}</code>.geojson?page={page_number}&page_size={page_size_number}
  </pre>

Example
^^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/data/28058.geojson?page=1&page_size=2

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
