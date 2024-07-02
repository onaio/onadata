# -*- coding: utf-8 -*-
"""
SqlTimingMiddleware - log SQL execution times per request.
"""
import logging

from django.db import connection

SQL_LOG = logging.getLogger("sql_logger")
TOTALS_LOG = logging.getLogger("sql_totals_logger")

# modified from
# http://johnparsons.net/index.php/2013/08/15/easy-sql-query-counting-in-django


class SqlTimingMiddleware:  # pylint: disable=too-few-public-methods
    """
    Logs the time taken by each sql query over requests.
    Logs the total time taken to run sql queries and the number of sql queries
    per request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_info = f"{request.method} {request.path_info}"
        response = self.get_response(request)
        sqltime = 0  # Variable to store execution time
        for query in connection.queries:
            # Add the time that the query took to the total
            sqltime += float(query["time"])
            SQL_LOG.debug(path_info, extra=query)

        TOTALS_LOG.debug(
            path_info, extra={"time": sqltime, "num_queries": len(connection.queries)}
        )

        return response
