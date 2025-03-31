# -*- coding: utf-8 -*-
"""
Audit model
"""
import json

from django.db import connection, models
from django.utils.translation import gettext as _

import six

DEFAULT_LIMIT = 1000


class Audit(models.Model):
    """
    Audit model - persists audit logs.
    """

    # pylint: disable=no-member
    json = models.JSONField()

    class Meta:
        app_label = "main"


class AuditLog:
    """
    AuditLog - creates and provide access to the Audit model records.
    """

    ACCOUNT = "account"
    DEFAULT_BATCHSIZE = 1000
    CREATED_ON = "created_on"

    def __init__(self, data):
        self.data = data

    def save(self):
        """
        Persists an audit to the DB
        """
        audit = Audit(json=self.data)
        audit.save()

        return audit

    @classmethod
    def query_iterator(cls, sql, fields=None, params=None, count=False):
        """
        Returns an iterator of all records.
        """

        # cursor seems to stringify dicts
        # added workaround to parse stringified dicts to json
        def parse_json(data):
            """Helper function to return a JSON string ``data`` as a python object."""
            try:
                return json.loads(data)
            except ValueError:
                return data

        params = params if params is not None else []
        cursor = connection.cursor()
        sql_params = fields + params if fields is not None else params

        if count:
            from_pos = sql.upper().find(" FROM")
            if from_pos != -1:
                sql = "SELECT COUNT(*) " + sql[from_pos:]

            order_pos = sql.upper().find("ORDER BY")
            if order_pos != -1:
                sql = sql[:order_pos]

            sql_params = params
            fields = ["count"]

        cursor.execute(sql, sql_params)

        if fields is None:
            for row in cursor.fetchall():
                yield parse_json(row[0])
        else:
            for row in cursor.fetchall():
                yield dict(zip(fields, row))

    # pylint: disable=too-many-locals,too-many-branches
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    @classmethod
    def query_data(
        cls,
        username,
        query=None,
        fields=None,
        sort=None,
        start=0,
        limit=DEFAULT_LIMIT,
        count=False,
    ):
        """
        Queries the Audit model and returns an iterator of the records.
        """
        if start is not None and (start < 0 or limit < 0):
            raise ValueError(_("Invalid start/limit params"))

        sort = "pk" if sort is None else sort
        instances = Audit.objects.filter().extra(
            where=["json->>%s = %s"], params=["account", username]
        )

        where_params = []
        sql_where = ""
        where = []
        if query and isinstance(query, six.string_types):
            query = json.loads(query)
            or_where = []
            or_params = []
            if "$or" in list(query):
                or_dict = query.pop("$or")
                for or_query in or_dict:
                    or_where.extend(["json->>%s = %s" for i in or_query.items()])
                    [  # pylint: disable=expression-not-assigned
                        or_params.extend(i) for i in or_query.items()
                    ]

                or_where = ["".join(["(", " OR ".join(or_where), ")"])]

            where = ["json->>%s = %s" for i in query.items()] + or_where
            for i in query.items():
                where_params.extend(i)
            where_params.extend(or_params)

        if fields and isinstance(fields, six.string_types):
            fields = json.loads(fields)

        if fields:
            field_list = ["json->%s" for i in fields]
            sql = f"SELECT {','.join(field_list)} FROM main_audit"

            if where_params:
                sql_where = " AND " + " AND ".join(where)

            sql += " WHERE json->>%s = %s " + sql_where + " ORDER BY id"
            params = ["account", username] + where_params

            if start is not None:
                sql += " OFFSET %s LIMIT %s"
                params += [start, limit]
            records = cls.query_iterator(sql, fields, params, count)
        else:
            if count:
                return [{"count": instances.count()}]

            if where_params:
                instances = instances.extra(where=where, params=where_params)

            records = instances.values_list("json", flat=True)

            sql, params = records.query.sql_with_params()

            if isinstance(sort, six.string_types) and sort:
                direction = "DESC" if sort.startswith("-") else "ASC"
                sort = sort[1:] if sort.startswith("-") else sort
                sql = f"{sql} ORDER BY json->>%s {direction}"
                params += (sort,)

            if start is not None:
                # some inconsistent/weird behavior I noticed with django's
                # queryset made me have to do a raw query
                # records = records[start: limit]
                sql = f"{sql} OFFSET %s LIMIT %s"
                params += (start, limit)

            records = cls.query_iterator(sql, None, list(params))

        return records
