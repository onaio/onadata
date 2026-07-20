Messaging
*********

This endpoint provides access to event messages sent for a specific target. Where:

* ``target_type`` - The type of the target object. The supported target types are:
    - ``xform``

    - ``project``

    - ``user``

    - ``kmskey``

    - ``entitylist``

* ``target_id`` - The unique identifier of the target object.

* ``verb`` - A specific action that has occured on the object. The supported verbs are:
    - ``message``

    - ``submission_created``

    - ``submission_edited``

    - ``submission_deleted``

    - ``submission_reviewed``

    - ``form_updated``

    - ``kmskey_rotated``

    - ``export_created``

    - ``export_downloaded``

    - ``entitylist_imported``

    - ``entitylist_deleted``


GET All event messages that have been sent for a form
------------------------------------------------------

Lists the events messages that have been sent for a specific form.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/messaging?target_type=<code>{type}</code>&target_id=<code>{form_id}</code>

Example
^^^^^^^^

::

    curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1


Response
^^^^^^^^^
::

    [
        {
            "id": 16485370,
            "verb": "message",
            "message": "Hey there",
            "user": "bob",
            "timestamp": "2021-02-26T03:32:57.799647-05:00"
        },
        {
            "id": 16484965,
            "verb": "submission_deleted",
            "message": "{\"id\": [\"71470149\"]}",
            "user": "bob",
            "timestamp": "2021-02-26T03:28:19.512875-05:00"
        },
        {
            "id": 12778522,
            "verb": "submission_edited",
            "message": "{\"id\": [71472574]}",
            "user": "bob",
            "timestamp": "2020-12-14T02:57:23.454169-05:00"
        },
        {
            "id": 12778520,
            "verb": "submission_created",
            "message": "{\"id\": [71472574]}",
            "user": "bob",
            "timestamp": "2020-12-14T02:57:23.264655-05:00"
        }
    ]

GET List of events that have occured on a form for a specific verb
------------------------------------------------------------------

Lists out all messages sent for a specific ``verb``.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/messaging?target_type=<code>{type}</code>&target_id=<code>{form_id}</code>&verb=<code>{message}</code>
  </pre>

Example
^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&verb=message


Response
^^^^^^^^^
::

    [
        {
            "id": 16485370,
            "verb": "message",
            "message": "Hey there",
            "user": "bob",
            "timestamp": "2021-02-26T03:32:57.799647-05:00"
        },
        {
            "id": 16485370,
            "verb": "message",
            "message": "lorem ipsum",
            "user": "bob",
            "timestamp": "2021-02-26T03:49:57.799647-05:00"
        }
    ]

GET Paginate events messages for a specific verb
------------------------------------------------

Lists out event messages using page number and the number of items per page. Use the ``page`` parameter to specify page number and ``page_size`` parameter is used to set the custom page size.

- ``page`` - Integer representing the page.
- ``page_size`` - Integer representing the number of records that should be returned in a single page.

There are a few important facts to note about retrieving paginated data:

#. The maximum number of items that can be requested in a page via the ``page_size`` query param is 10,000
#. Information regrading transversal of the paginated responses can be found in `the Link header <https://tools.ietf.org/html/rfc5988>`_ returned in the response. *Note: Some relational links may not be present depending on the page accessed i.e the ``first`` relational page link won't be present on the first page response*

Example
^^^^^^^^
::

      curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&verb=message&page=1&page_size=1

Sample response with link header
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Response Header:** ::

      ...
      Link: <https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&verb=message&page=2&page_size=1>; rel="next", <https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&verb=message&page=3&page_size=1>; rel="last"

**Response:** ::

      [
          {
              "id": 16485370,
              "verb": "message",
              "message": "Hey there",
              "user": "bob",
              "timestamp": "2021-02-26T03:32:57.799647-05:00"
          }
      ]

GET Grouped activity counts
---------------------------

Passing one or more ``group_by`` parameters returns activity counts instead of
individual event messages, grouped by the requested dimension(s). The supported
dimensions are ``user``, ``verb`` and a time bucket (one of ``hour``, ``day``,
``week``, ``month`` or ``year``); repeat the parameter to combine them. At most
one time bucket may be combined per request. The same ``target_type``,
``target_id`` and optional ``user`` filters apply. The results are paginated and
ordered by most recent activity first. Any other ``group_by`` value, or more
than one time bucket, returns an HTTP 400 response.

- ``group_by=verb`` - Counts per verb, aggregated across users.
- ``group_by=user`` - Counts per user, aggregated across verbs.
- ``group_by=user&group_by=verb`` - Counts per ``(user, verb)``.
- ``group_by=day`` - Counts per UTC day, aggregated across users and verbs.
- ``group_by=day&group_by=user&group_by=verb`` - Counts per
  ``(day, user, verb)``.

Each row always contains:

- ``count`` - The number of events in the group.
- ``earliest_timestamp`` - The timestamp of the oldest event in the group.
- ``latest_timestamp`` - The timestamp of the most recent event in the group.

The requested dimensions are also included in each row:

- ``period_start`` - The UTC start of the time bucket. Only present when a time
  bucket was requested. Time bucket boundaries are computed in UTC.
- ``user`` - The username of the acting user. This is ``null`` when the actor
  id no longer resolves to a user.
- ``verb`` - The action that occurred on the target.

All timestamps in grouped responses are rendered in UTC. Because a time bucket
also reports ``earliest_timestamp`` and ``latest_timestamp``, a client can
render an event range (e.g. "15 submissions from 09:00 to 10:00") by merging
adjacent buckets; the endpoint does not collapse bursts on the server.

.. raw:: html

  <pre class="prettyprint">
  <b>GET</b> /api/v1/messaging?target_type=<code>{type}</code>&target_id=<code>{form_id}</code>&group_by=<code>day</code>&group_by=<code>user</code>&group_by=<code>verb</code>
  </pre>

Example
^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&group_by=day&group_by=user&group_by=verb


Response
^^^^^^^^^
::

    [
        {
            "period_start": "2026-03-15T00:00:00Z",
            "user": "bob",
            "verb": "submission_created",
            "count": 14,
            "earliest_timestamp": "2026-03-15T06:10:00Z",
            "latest_timestamp": "2026-03-15T18:22:57Z"
        },
        {
            "period_start": "2026-03-14T00:00:00Z",
            "user": "bob",
            "verb": "submission_edited",
            "count": 2,
            "earliest_timestamp": "2026-03-14T02:57:23Z",
            "latest_timestamp": "2026-03-14T09:41:05Z"
        }
    ]

Query events of a target using timestamp
----------------------------------------

Filter messages using the timestamp field. To filter messages by their timestamp, the `timestamp` parameter is appended to the messaging endpoint URL.
This allows for precise retrieval of events that occurred within specific time frames or ranges.

Example
^^^^^^^^
::

    curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1&verb=submission_edited&timestamp__lte=2024-06-20T00:00

Where:

- ``target_type=xform`` - The target object type is xform
- ``target_id=1`` - The target object unique id, in this case the xform ID
- ``verb=submission_edited`` - The action occured on the xform, in this case a submission in the xform has been edited
- ``timestamp__lte=2024-06-20T00:00`` - Filters the events/messages to include only those that occurred on or before June 20, 2024, at 00:00 (midnight).

Timestamp field Filters Options

=============================     ===================================
Filter                            Description
=============================     ===================================
**timestamp__year**               Exact year e.g. 2024
**timestamp__year__lt**           Year Less than
**timestamp__year__lte**          Year Less than or Equal to
**timestamp__year__gt**           Year Greater than
**timestamp__year__gte**          Year Greater than or Equal to
**timestamp__month**              Exact month e.g. 10
**timestamp__month__lt**          Month Less than
**timestamp__month__lte**         Month Less than or Equal to
**timestamp__month__gt**          Month Greater than
**timestamp__month__gte**         Month Greater than or Equal to
**timestamp__day**                Exact day e.g. 12
**timestamp__day__lt**            Day Less than
**timestamp__day__lte**           Day Less than or Equal to
**timestamp__day__gt**            Day Greater than
**timestamp__day__gte**           Day Greater than or Equal to
=============================     ===================================
