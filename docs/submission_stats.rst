Submission Stats
*****************

Provides submissions counts grouped by a specified field.
It accepts query parameters `group` and `name`. Default result
is grouped by `_submission_time`, hence you get submission counts per day.
If a date field is used as the group, the result will be grouped by day.

* *group* - field to group submission counts by
* *name* - name to be applied to the group on results

Example
^^^^^^^^^
::

       GET /api/v1/stats/submissions/1?group=_submission_time&name=day_of_submission


Response
^^^^^^^^^
::

          [
              {
                  "count": 8,
                  "day_of_submission": "2013-11-15",
              },
              {
                  "count": 99,
                  "day_of_submission": "2013-11-16",
              },
              {
                  "count": 133,
                  "day_of_submission": "2013-11-17",
              },
              {
                  "count": 162,
                  "day_of_submission": "2013-11-18",
              },
              {
                  "count": 102,
                  "day_of_submission": "2013-11-19",
              }
          ]