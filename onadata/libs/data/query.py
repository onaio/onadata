from django.conf import settings
from django.db import connection

from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.apps.logger.models.data_view import DataView


def _dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description

    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def _execute_query(query, to_dict=True):
    cursor = connection.cursor()
    cursor.execute(query)

    return _dictfetchall(cursor) if to_dict else cursor


def _get_fields_of_type(xform, types):
    k = []
    survey_elements = flatten(
        [xform.get_survey_elements_of_type(t) for t in types])

    for element in survey_elements:
        name = element.get_abbreviated_xpath()
        k.append(name)

    return k


def _additional_data_view_filters(data_view):
    where, where_params = DataView._get_where_clause(data_view)

    data_view_where = ""
    if where:
        data_view_where = u" AND " + u" AND ".join(where)

    for it in where_params:
        data_view_where = data_view_where.replace('%s', "'{}'".format(it), 1)

    return data_view_where


def _json_query(field):
    return "json->>'%s'" % field


def _postgres_count_group_field_n_group_by(field, name, xform, group_by,
                                           data_view):
    string_args = _query_args(field, name, xform, group_by)
    if is_date_field(xform, field):
        string_args['json'] = "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY"\
                              "-MM-DD')" % string_args

    additional_filters = ""
    if data_view:
        additional_filters = _additional_data_view_filters(data_view)

    query = "SELECT %(json)s AS \"%(name)s\", "\
            "%(group_by)s AS \"%(group_name)s\", "\
            "count(*) as count "\
            "FROM %(table)s WHERE %(restrict_field)s=%(restrict_value)s " \
            "AND deleted_at IS NULL " + additional_filters + \
            " GROUP BY %(json)s, %(group_by)s" + \
            " ORDER BY %(json)s, %(group_by)s"
    query = query % string_args

    return query


def _postgres_count_group(field, name, xform, data_view=None):
    string_args = _query_args(field, name, xform)
    if is_date_field(xform, field):
        string_args['json'] = "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY"\
                              "-MM-DD')" % string_args

    additional_filters = ""
    if data_view:
        additional_filters = _additional_data_view_filters(data_view)

    sql_query = "SELECT %(json)s AS \"%(name)s\", COUNT(*) AS count FROM "" \
    ""%(table)s WHERE %(restrict_field)s=%(restrict_value)s "" \
    "" AND deleted_at IS NULL " + additional_filters + " GROUP BY %(json)s" \
        " ORDER BY %(json)s"
    sql_query = sql_query % string_args

    return sql_query


def _postgres_aggregate_group_by(field, name, xform, group_by, data_view=None):
    string_args = _query_args(field, name, xform, group_by)
    if is_date_field(xform, field):
        string_args['json'] = "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY"\
                              "-MM-DD')" % string_args

    additional_filters = ""
    if data_view:
        additional_filters = _additional_data_view_filters(data_view)

    group_by_select = ""
    group_by_group_by = ""
    if isinstance(group_by, list):
        group_by_group_by = []
        for i, v in enumerate(group_by):
            group_by_select += "%(group_by" + str(i) + \
                    ")s AS \"%(group_name" + str(i) + ")s\", "
            group_by_group_by.append("%(group_by" + str(i) + ")s")
        group_by_group_by = ",".join(group_by_group_by)
    else:
        group_by_select = "%(group_by)s AS \"%(group_name)s\","
        group_by_group_by = "%(group_by)s"

    query = "SELECT " + group_by_select + \
            "SUM((%(json)s)::numeric) AS sum, " \
            "AVG((%(json)s)::numeric) AS mean  " \
            "FROM %(table)s WHERE %(restrict_field)s=%(restrict_value)s " \
            "AND deleted_at IS NULL " + additional_filters + \
            " GROUP BY " + group_by_group_by + \
            " ORDER BY " + group_by_group_by

    query = query % string_args

    return query


def _postgres_select_key(field, name, xform):
    string_args = _query_args(field, name, xform)

    return "SELECT %(json)s AS \"%(name)s\" FROM %(table)s WHERE "\
           "%(restrict_field)s=%(restrict_value)s AND deleted_at IS NULL "\
           % string_args


def _query_args(field, name, xform, group_by=None):
    qargs = {
        'table': 'logger_instance',
        'json': _json_query(field),
        'name': name,
        'restrict_field': 'xform_id',
        'restrict_value': xform.pk}

    if isinstance(group_by, list):
        for i, v in enumerate(group_by):
            qargs['group_name%d' % i] = v
            qargs['group_by%d' % i] = _json_query(v)
    else:
        qargs['group_name'] = group_by
        qargs['group_by'] = _json_query(group_by)

    return qargs


def _select_key(field, name, xform):
    if using_postgres:
        result = _postgres_select_key(field, name, xform)
    else:
        raise Exception("Unsupported Database")

    return result


def flatten(l):
    return [item for sublist in l for item in sublist]


def get_date_fields(xform):
    """List of date field names for specified xform"""
    return [SUBMISSION_TIME] + _get_fields_of_type(
        xform, ['date', 'datetime', 'start', 'end', 'today'])


def get_field_records(field, xform):
    result = _execute_query(_select_key(field, field, xform),
                            to_dict=False)
    return [float(i[0]) for i in result if i[0] is not None]


def get_form_submissions_grouped_by_field(xform, field, name=None,
                                          data_view=None):
    """Number of submissions grouped by field"""
    if not name:
        name = field

    return _execute_query(_postgres_count_group(field, name, xform, data_view))


def get_form_submissions_aggregated_by_select_one(xform, field, name=None,
                                                  group_by=None,
                                                  data_view=None):
    """Number of submissions grouped and aggregated by select_one field"""
    if not name:
        name = field
    return _execute_query(_postgres_aggregate_group_by(field,
                                                       name,
                                                       xform,
                                                       group_by,
                                                       data_view))


def get_form_submissions_grouped_by_select_one(xform, field, group_by,
                                               name=None, data_view=None):
    """Number of submissions disaggregated by select_one field"""
    if not name:
        name = field
    return _execute_query(_postgres_count_group_field_n_group_by(field,
                                                                 name,
                                                                 xform,
                                                                 group_by,
                                                                 data_view))


def get_numeric_fields(xform):
    """List of numeric field names for specified xform"""
    return _get_fields_of_type(xform, ['decimal', 'integer'])


def is_date_field(xform, field):
    return field in get_date_fields(xform)


@property
def using_postgres():
    return settings.DATABASES[
        'default']['ENGINE'] == 'django.db.backends.postgresql_psycopg2'
