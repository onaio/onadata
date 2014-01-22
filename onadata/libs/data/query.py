from django.conf import settings
from django.db import connection
from django.utils.translation import ugettext as _

from onadata.libs.utils.common_tags import SUBMISSION_TIME


def _count_group(field, name, xform):
    if using_postgres:
        result = _postgres_count_group(field, name, xform)
    else:
        raise Exception("Unsupported Database")

    return result


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
    dd = xform.data_dictionary()
    survey_elements = flatten(
        [dd.get_survey_elements_of_type(t) for t in types])

    for element in survey_elements:
        name = element.get_abbreviated_xpath()
        k.append(name)

    return k


def _json_query(field):
    return "json->>'%s'" % field


def _postgres_count_group(field, name, xform):
    string_args = _query_args(field, name, xform)
    if is_date_field(xform, field):
        string_args['json'] = "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY"\
                              "-MM-DD')" % string_args

    return "SELECT %(json)s AS %(name)s, COUNT(*) AS count FROM "\
           "%(table)s WHERE %(restrict_field)s=%(restrict_value)s "\
           "GROUP BY %(json)s" % string_args


def _postgres_select_key(field, name, xform):
    string_args = _query_args(field, name, xform)

    return "SELECT %(json)s AS %(name)s FROM %(table)s WHERE "\
           "%(restrict_field)s=%(restrict_value)s" % string_args


def _query_args(field, name, xform):
    return {
        'table': 'odk_logger_instance',
        'json': _json_query(field),
        'name': name,
        'restrict_field': 'xform_id',
        'restrict_value': xform.pk}


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


def get_form_submissions_grouped_by_field(xform, field, name=None):
    """Number of submissions grouped by field"""
    if not name:
        name = field

    result = _execute_query(_count_group(field, name, xform))

    # if we have a single None result, the field doesnt exist
    #if len(result) == 1 and result[0][name] is None:
        #raise ValueError(_(
            #u"Field '{}' does not exist in result {}".format(field, result)))
    #elif len(result) > 0 and result[0][name] is None:
    #    # strip out the first result if it has a count of 0 and value of None
    #    result = result[1:]

    return result


def get_numeric_fields(xform):
    """List of numeric field names for specified xform"""
    return _get_fields_of_type(xform, ['decimal', 'integer'])


def is_date_field(xform, field):
    return field in get_date_fields(xform)


@property
def using_postgres():
    return settings.DATABASES[
        'default']['ENGINE'] == 'django.db.backends.postgresql_psycopg2'
