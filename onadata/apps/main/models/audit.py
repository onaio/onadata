import json
import six

from django.db import models
from django.db import connection
from django.contrib.postgres.fields import JSONField
from django.utils.translation import ugettext as _

DEFAULT_LIMIT = 1000


class Audit(models.Model):
    json = JSONField()

    class Meta:
        app_label = 'main'


class AuditLog(object):
    ACCOUNT = u"account"
    DEFAULT_BATCHSIZE = 1000
    CREATED_ON = u"created_on"

    def __init__(self, data):
        self.data = data

    def save(self):
        a = Audit(json=self.data)
        a.save()

        return a

    @classmethod
    def query_iterator(cls, sql, fields=None, params=[], count=False):
        cursor = connection.cursor()
        sql_params = fields + params if fields is not None else params

        if count:
            from_pos = sql.upper().find(' FROM')
            if from_pos != -1:
                sql = u"SELECT COUNT(*) " + sql[from_pos:]

            order_pos = sql.upper().find('ORDER BY')
            if order_pos != -1:
                sql = sql[:order_pos]

            sql_params = params
            fields = [u'count']

        cursor.execute(sql, sql_params)

        if fields is None:
            for row in cursor.fetchall():
                yield row[0]
        else:
            for row in cursor.fetchall():
                yield dict(zip(fields, row))

    @classmethod
    def query_data(cls, username, query=None, fields=None, sort=None, start=0,
                   limit=DEFAULT_LIMIT, count=False):
        if start is not None and (start < 0 or limit < 0):
            raise ValueError(_("Invalid start/limit params"))

        sort = 'pk' if sort is None else sort
        instances = Audit.objects.filter().extra(where=["json->>%s = %s"],
                                                 params=['account', username])

        where_params = []
        sql_where = u""
        if query and isinstance(query, six.string_types):
            query = json.loads(query)
            or_where = []
            or_params = []
            if '$or' in list(query):
                or_dict = query.pop('$or')
                for l in or_dict:
                    or_where.extend([u"json->>%s = %s" for i in l.items()])
                    [or_params.extend(i) for i in l.items()]

                or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

            where = [u"json->>%s = %s" for i in query.items()] + or_where
            [where_params.extend(i) for i in query.items()]
            where_params.extend(or_params)

        if fields and isinstance(fields, six.string_types):
            fields = json.loads(fields)

        if fields:
            field_list = [u"json->%s" for i in fields]
            sql = u"SELECT %s FROM main_audit" % u",".join(field_list)

            if where_params:
                sql_where = u" AND " + u" AND ".join(where)

            sql += u" WHERE json->>%s = %s " + sql_where \
                + u" ORDER BY id"
            params = ['account', username] + where_params

            if start is not None:
                sql += u" OFFSET %s LIMIT %s"
                params += [start, limit]
            records = cls.query_iterator(sql, fields, params, count)
        else:
            if count:
                return [{"count": instances.count()}]

            if where_params:
                instances = instances.extra(where=where, params=where_params)

            records = instances.values_list('json', flat=True)

            sql, params = records.query.sql_with_params()

            if isinstance(sort, six.string_types) and len(sort) > 0:
                direction = 'DESC' if sort.startswith('-') else 'ASC'
                sort = sort[1:] if sort.startswith('-') else sort
                sql = u'{} ORDER BY json->>%s {}'.format(sql, direction)
                params += (sort,)

            if start is not None:
                # some inconsistent/weird behavior I noticed with django's
                # queryset made me have to do a raw query
                # records = records[start: limit]
                sql = u"{} OFFSET %s LIMIT %s".format(sql)
                params += (start, limit)

            records = cls.query_iterator(sql, None, list(params))

        return records
