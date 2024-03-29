Messaging
*********

This endpoint provides access to event messages sent for a specific target. Where:

* ``target_type`` - The type of the target object. The supported target types are:
    - ``xform``

    - ``project``

    - ``user``

* ``target_id`` - The unique identifier of the target object.

* ``verb`` - A specific action that has occured on the object. The supported verbs are:
    - ``message``

    - ``submission_created``

    - ``submission_edited``

    - ``submission_deleted``

    - ``submission_reviewed``

    - ``form_updated``


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
