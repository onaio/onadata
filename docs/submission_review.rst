SubmissionReview
****************

This endpoint supports List, Retrieve, Update, Create Submission Reviews

Where:

- ``id`` - the id of the submission review (required when doing an update)
- ``instance`` - the id of the Instance object being reviewed
- ``note`` - the submission review comment
- ``status`` - the submission review status. Should be one of:

    - ``'1'`` - approved
    - ``'2'`` - rejected
    - ``'3'`` - pending

Note must be provided incase the status in '2' (rejected)

Make a Submission Review
------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissionreview.json</pre>

Example
^^^^^^^
::

    curl -X POST -H "Content-type:application/json" -d '{"status":"1","instance":1337,"note":"This was approved because it is awesome!"}' https://example.com/api/v1/submissionreview.json

Response
^^^^^^^^^
::

    {
        "id": 4,
        "instance": 1337,
        "created_by": 2,
        "status": "1",
        "date_created": "2019-07-18T08:25:54.536762-04:00",
        "note": "This was approved because it is awesome!",
        "date_modified": "2019-07-18T08:25:54.536785-04:00"
    }


Update a Submission Review
--------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>PUT</b> /api/v1/submissionreview/<code>{id}</code>.json</pre>

Example
^^^^^^^
::

    curl -X PUT -H "Content-type:application/json" -d '{"id": 4,"instance": 1337,"created_by": 2,"status": "3","date_created": "2019-07-18T08:25:54.536762-04:00","note": "Returned to pending!","date_modified": "2019-07-18T08:25:54.536785-04:00"}' https://example.com/api/v1/submissionreview/4.json

Response
^^^^^^^^^
::

    {
        "id": 4,
        "instance": 1337,
        "created_by": 2,
        "status": "3",
        "date_created": "2019-07-18T08:25:54.536762-04:00",
        "note": "Returned to pending!",
        "date_modified": "2019-07-18T08:25:54.536785-04:00"
    }


Delete a Submission Review
--------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>DELETE</b> /api/v1/submissionreview/<code>{id}</code>.json</pre>

Example
^^^^^^^
::

    curl -X DELETE https://example.com/api/v1/submissionreview/4.json

Response
^^^^^^^^^
::

    HTTP 204 NO CONTENT


Retrieve a Submission Review
----------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/submissionreview/<code>{id}</code>.json</pre>

Example
^^^^^^^
::

    curl -X GET https://example.com/api/v1/submissionreview/4.json

Response
^^^^^^^^^
::

    {
        "id": 4,
        "instance": 1337,
        "created_by": 2,
        "status": "3",
        "date_created": "2019-07-18T08:25:54.536762-04:00",
        "note": "Returned to pending!",
        "date_modified": "2019-07-18T08:25:54.536785-04:00"
    }

Get a List of Submission Reviews
--------------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>GET</b> /api/v1/submissionreview/.json</pre>

Example
^^^^^^^
::

    curl -X GET https://example.com/api/v1/submissionreview/.json

Response
^^^^^^^^^
::

    [
        {
            "id": 1,
            "instance": 10,
            "created_by": 2,
            "status": "1",
            "date_created": "2019-06-13T03:02:52.485116-04:00",
            "note": "null",
            "date_modified": "2019-06-13T03:02:52.485140-04:00"
        },
        {
            "id": 2,
            "instance": 11,
            "created_by": 2,
            "status": "1",
            "date_created": "2019-06-13T03:19:46.127652-04:00",
            "date_modified": "2019-06-13T03:19:46.127686-04:00"
        } ...
    ]

Bulk Create Submission Review
-----------------------------
.. raw:: html

    <pre class="prettyprint">
    <b>POST</b> /api/v1/submissionreview.json</pre>

Example
^^^^^^^
::

    curl -X POST -H "Content-type:application/json" -d '[{"status":"1","instance":1337,"note":"This was approved because it is awesome!"},{"status":"1","instance":1338}]' https://example.com/api/v1/submissionreview.json

Response
^^^^^^^^^
::

    [
        {
            "id": 5,
            "instance": 1337,
            "created_by": 2,
            "status": "1",
            "date_created": "2019-07-18T09:25:33.795161-04:00",
            "note": "This was approved because it is awesome!",
            "date_modified": "2019-07-18T09:25:33.795182-04:00"
        },
        {
            "id": 6,
            "instance": 1338,
            "created_by": 2,
            "status": "1",
            "date_created": "2019-07-18T09:25:33.917456-04:00",
            "date_modified": "2019-07-18T09:25:33.917484-04:00"
        }
    ]

Filtering by Instance
---------------------

Example
^^^^^^^
::

    curl -X GET -H "Content-Type:application/json" https://example.com/api/v1/submissionreview/?instance=66


Filtering by Status
---------------------

Example
^^^^^^^
::

    curl -X GET -H "Content-Type:application/json" https://example.com/api/v1/submissionreview/?status=2

