Messaging Stats
****************

Provides a count of each unique messaging event grouped by either day, month or year.

All requests require authentication and the same target read permissions as
:doc:`messaging`, including organization owner/manager access to organization
user feeds. Permission checks run before streaming, including for empty results.
Missing target parameters or unknown types return ``400``; malformed or
nonexistent target IDs return ``404``; unauthorized targets return ``403``.
Deleted targets, targets in deleted projects, inactive user accounts, and
targets belonging to inactive organizations also return ``404``.
Responses are private and must not be cached.

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
