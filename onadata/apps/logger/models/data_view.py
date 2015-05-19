import json
import six
import datetime

from django.contrib.gis.db import models
from django.db import connection

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from jsonfield import JSONField
from onadata.libs.utils.common_tags import MONGO_STRFTIME


def _json_sql_str(key, known_integers=[], known_dates=[]):
    _json_str = u"json->%s"

    if key in known_integers:
        _json_str = u"CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = u"CAST(json->>%s AS TIMESTAMP)"

    return _json_str

def get_name_from_survey_element(element):
    return element.get_abbreviated_xpath()

class DataView(models.Model):
    """
    Model to provide filtered access to the underlying data of an XForm
    """
    name = models.CharField(max_length=255)
    xform = models.ForeignKey(XForm)
    project = models.ForeignKey(Project)

    columns = JSONField()
    query = JSONField()

    class Meta:
        app_label = 'logger'

    @classmethod
    def _get_where_clause(cls, data_view, form_integer_fields=[]):
        known_integers = ['_id'] + form_integer_fields
        known_dates = ['_submission_time']
        where = []
        where_params = []

        query = data_view.query

        or_where = []
        or_params = []

        #if '$or' in query.keys():
        #    or_dict = query.pop('$or')
        #    for l in or_dict:
        #        or_where.extend([u"json->>%s = %s" for i in l.items()])
        #        [or_params.extend(i) for i in l.items()]

        #    or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

        # where = [u"json->>%s = %s" for i in query.items()] + or_where
        for q in query:
            filter = q.get('filter')
            col = q.get('col')
            value = q.get('value')
            json_str = _json_sql_str(col, known_integers, known_dates)

            if filter == '=':
                where.append(u"{} = %s".format(json_str))
            if filter == '>':
                where.append(u"{} > %s".format(json_str))
            if filter == '<':
                where.append(u"{} < %s".format(json_str))
            if filter == '>=':
                where.append(u"{} >= %s".format(json_str))
            if filter == '<=':
                where.append(u"{} <= %s".format(json_str))

            if filter in known_dates:
                value = datetime.datetime.strptime(
                    value[:19], MONGO_STRFTIME)

            where_params.extend((col, unicode(value)))

        where += or_where
        where_params.extend(or_params)

        return where, where_params

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

        cursor.execute(sql, [unicode(i) for i in sql_params])

        if fields is None:
            for row in cursor.fetchall():
                yield row[0]
        else:
            for row in cursor.fetchall():
                yield dict(zip(fields, row))

    @classmethod
    def query_data(cls, data_view):

        # get the columns needed
        columns = data_view.columns
        query = data_view.query

        sql_where = ""
        where_params = []

        field_list = [u"json->%s" for i in columns]

        sql = u"SELECT %s FROM logger_instance" % u",".join(field_list)

        data_dictionary = data_view.xform.data_dictionary()
        known_integers = [
            get_name_from_survey_element(e)
            for e in data_dictionary.get_survey_elements_of_type('integer')]

        where, where_params = cls._get_where_clause(data_view, known_integers)

        sql_where = u" AND " + u" AND ".join(where)

        sql += u" WHERE xform_id = %s " + sql_where + u" AND deleted_at IS NULL"
        params = [data_view.xform.pk] + where_params

        records =[record for record in DataView.query_iterator(sql,
                                                               fields=columns,
                                                               params=params)]

        return records


