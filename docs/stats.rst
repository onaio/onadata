Stats
*******

Stats List
================

Stats summary for median, mean, mode, range, max, min. A query parameter ``method`` can be used to limit the results to either ``mean``, ``median``, ``mode`` or ``range`` only results.

Example
^^^^^^^
::

    GET /api/v1/stats/1

Response:
^^^^^^^^^
::

    [
        {
            "age": {
                "median": 8,
                "mean": 23.4,
                "mode": 23,
                "range": 24,
                "max": 28,
                "min": 4
            },
            ...
        },
        ...
    ]

Example:
^^^^^^^^
::

    GET /api/v1/stats/1?method=median

Response:
^^^^^^^^^
::

    [
        {
            "age": {
                "median": 8,
            },
            ...
        },
        ...
    ]
