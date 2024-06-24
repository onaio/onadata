Messaging Stats
****************

Provides a count of each unique messaging event grouped by either day, month or year.

The endpoint accepts the following *required* query parameters:

* *group_by* - field specifying whether to group events by `day`, `month` or `year`.

* *target_type* - field to be used to determine the target object type i.e `xform`.

* *target_id* - field used to identify the target object - e.g. for `XForm` this is the `id` field.

* *verb*: field used to filter returned responses by a specific verb.

* *timestamp*: used to filter by actions that occurred in a specific timeframe. This query parameter support date time lookups i.e `timestamp__day`, `timestamp__year`.

Example
^^^^^^^^
::

        GET /api/v1/stats/messaging?target_id=1&target_type=xform&group_by=year

Response
^^^^^^^^^
::

        [
          {
            "submission_edited": 5,
            "submission_created": 10,
            "group": "2023"
          },
          {
            "submission_edited": 1043,
            "submission_created": 5023,
            "submission_deleted": 200,
            "group": "2022"
          },
        ]
