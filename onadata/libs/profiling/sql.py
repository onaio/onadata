# -*- coding: utf-8 -*-
"""
SqlTimingMiddleware - log SQL execution times per request.
"""
import logging

from django.db import connection

sql_log = logging.getLogger('sql_logger')  # pylint: disable=C0103
totals_log = logging.getLogger('sql_totals_logger')  # pylint: disable=C0103

# modified from
# http://johnparsons.net/index.php/2013/08/15/easy-sql-query-counting-in-django


class SqlTimingMiddleware(object):  # pylint: disable=R0903
    """
    Logs the time taken by each sql query over requests.
    Logs the total time taken to run sql queries and the number of sql queries
    per request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_info = '%s %s' % (request.method, request.path_info)
        response = self.get_response(request)
        sqltime = 0  # Variable to store execution time
        for query in connection.queries:
            # Add the time that the query took to the total
            sqltime += float(query["time"])
            sql_log.debug(path_info, extra=query)

        totals_log.debug(
            path_info,
            extra={'time': sqltime,
                   'num_queries': len(connection.queries)})

        return response
