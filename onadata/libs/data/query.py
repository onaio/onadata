# -*- coding: utf-8 -*-
"""
Query data utility functions.
"""

import logging

from django.conf import settings
from django.db import connection

from onadata.apps.logger.models.data_view import DataView
from onadata.libs.utils.common_tags import SUBMISSION_TIME, SUBMITTED_BY
from onadata.libs.utils.common_tools import get_abbreviated_xpath

logger = logging.getLogger(__name__)


def _dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description

    return [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]


def _execute_query(query, params=None, to_dict=True):
    cursor = connection.cursor()
    # Pass ``None`` (not an empty list) when there are no parameters so the
    # driver sends the query verbatim and does not attempt ``%`` interpolation.
    cursor.execute(query, params or None)

    return _dictfetchall(cursor) if to_dict else cursor


def _get_fields_of_type(xform, types):
    k = []
    survey_elements = flatten([xform.get_survey_elements_of_type(t) for t in types])

    for element in survey_elements:
        name = get_abbreviated_xpath(element.get_xpath())
        k.append(name)

    return k


def _additional_data_view_filters(data_view):
    """Return a DataView's filter SQL fragment and its bound parameters.

    The fragment keeps the ``%s`` placeholders emitted by
    ``DataView._get_where_clause`` and the parameters are returned untouched so
    the caller can hand them to ``cursor.execute`` as bound values. No
    request-derived filter column or value is ever rendered into the SQL text.
    """
    # pylint: disable=protected-access
    where, where_params = DataView._get_where_clause(data_view)

    if not where:
        return "", []

    return " AND " + " AND ".join(where), list(where_params)


def _json_query(field):
    if not field:
        logger.info("Field is empty")
        return f"json->>'{field}'"

    _field = field.replace("'", "''")

    return f"json->>'{_field}'"


def _escape_identifier(value):
    """Escape a value used as a double-quoted SQL identifier/alias."""
    return value.replace('"', '""') if isinstance(value, str) else value


def _postgres_count_group_field_n_group_by(field, name, xform, group_by, data_view):
    string_args = _query_args(field, name, xform, group_by)
    if is_date_field(xform, field):
        string_args["json"] = (
            "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY" "-MM-DD')" % string_args
        )

    additional_filters, additional_params = "", []
    if data_view:
        additional_filters, additional_params = _additional_data_view_filters(data_view)
    string_args["additional_filters"] = additional_filters

    restricted_string = _restricted_query(xform)
    query = (
        'SELECT %(json)s AS "%(name)s", '
        '%(group_by)s AS "%(group_name)s", '
        "count(*) as count "
        "FROM %(table)s WHERE "
        + restricted_string
        + " AND deleted_at IS NULL "
        + "%(additional_filters)s"
        + " GROUP BY %(json)s, %(group_by)s"
        + " ORDER BY %(json)s, %(group_by)s"
    )
    query = query % string_args

    return query, additional_params


def _postgres_count_group(field, name, xform, data_view=None):
    string_args = _query_args(field, name, xform)
    if is_date_field(xform, field):
        string_args["json"] = (
            "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY" "-MM-DD')" % string_args
        )

    additional_filters, additional_params = "", []
    if data_view:
        additional_filters, additional_params = _additional_data_view_filters(data_view)
    string_args["additional_filters"] = additional_filters

    # Use left join to the auth user model for better performance.
    if field == SUBMITTED_BY:
        string_args["json"] = "au.username"
        string_args["join"] = "i LEFT JOIN auth_user au ON au.id = i.user_id"

    restricted_string = _restricted_query(xform)
    sql_query = (
        'SELECT %(json)s AS "%(name)s", COUNT(*) AS count FROM '
        "%(table)s %(join)s WHERE "
        + restricted_string
        + " AND deleted_at IS NULL "
        + "%(additional_filters)s"
        + " GROUP BY %(json)s"
        " ORDER BY %(json)s"
    )
    sql_query = sql_query % string_args

    return sql_query, additional_params


def _postgres_aggregate_group_by(field, name, xform, group_by, data_view=None):
    string_args = _query_args(field, name, xform, group_by)
    if is_date_field(xform, field):
        string_args["json"] = (
            "to_char(to_date(%(json)s, 'YYYY-MM-DD'), 'YYYY" "-MM-DD')" % string_args
        )

    additional_filters, additional_params = "", []
    if data_view:
        additional_filters, additional_params = _additional_data_view_filters(data_view)
    string_args["additional_filters"] = additional_filters

    group_by_select = ""
    group_by_group_by = ""
    if isinstance(group_by, list):
        group_by_group_by = []
        for i, __ in enumerate(group_by):
            group_by_select += (
                "%(group_by" + str(i) + ')s AS "%(group_name' + str(i) + ')s", '
            )
            group_by_group_by.append("%(group_by" + str(i) + ")s")
        group_by_group_by = ",".join(group_by_group_by)
    else:
        group_by_select = '%(group_by)s AS "%(group_name)s",'
        group_by_group_by = "%(group_by)s"

    restricted_string = _restricted_query(xform)
    aggregation_string = "COUNT(%(json)s) AS count "
    if field in get_numeric_fields(xform) or not isinstance(group_by, list):
        aggregation_string += (
            ", SUM((%(json)s)::numeric) AS sum, " "AVG((%(json)s)::numeric) AS mean "
        )
    else:
        group_by_select = "%(json)s AS %(name)s, " + group_by_select
        group_by_group_by = "%(json)s, " + group_by_group_by
    query = (
        "SELECT "
        + group_by_select
        + aggregation_string
        + "FROM %(table)s WHERE "
        + restricted_string
        + " AND deleted_at IS NULL "
        + "%(additional_filters)s"
        + " GROUP BY "
        + group_by_group_by
        + " ORDER BY "
        + group_by_group_by
    )

    return query % string_args, additional_params


def _postgres_select_key(field, name, xform):
    string_args = _query_args(field, name, xform)
    restricted_string = _restricted_query(xform)
    query = (
        'SELECT %(json)s AS "%(name)s" FROM %(table)s WHERE '
        + restricted_string
        + " AND deleted_at IS NULL "
    )
    return query % string_args


def _restricted_query(xform):
    if xform.is_merged_dataset:
        return "%(restrict_field)s IN %(restrict_value)s"

    return "%(restrict_field)s=%(restrict_value)s"


def _query_args(field, name, xform, group_by=None):
    qargs = {
        "table": "logger_instance",
        "json": _json_query(field),
        "name": _escape_identifier(name),
        "restrict_field": "xform_id",
        "restrict_value": xform.pk,
        "join": "",
    }

    if xform.is_merged_dataset:
        xforms = tuple(
            __
            for __ in xform.mergedxform.xforms.filter(
                deleted_at__isnull=True
            ).values_list("id", flat=True)
        ) or (xform.pk, xform.pk)
        qargs["restrict_value"] = xforms

    if isinstance(group_by, list):
        for index, value in enumerate(group_by):
            qargs[f"group_name{index}"] = _escape_identifier(value)
            qargs[f"group_by{index}"] = _json_query(value)
    else:
        qargs["group_name"] = _escape_identifier(group_by)
        qargs["group_by"] = _json_query(group_by)

    return qargs


def _select_key(field, name, xform):
    if using_postgres():
        return _postgres_select_key(field, name, xform)

    raise ValueError("Unsupported Database")


def flatten(lst):
    """Flattens a list of lists."""
    return [item for sublist in lst for item in sublist]


def get_date_fields(xform):
    """List of date field names for specified xform"""
    return [SUBMISSION_TIME] + _get_fields_of_type(
        xform, ["date", "datetime", "start", "end", "today"]
    )


def get_field_records(field, xform):
    """Queries and returns all records of the given field."""
    result = _execute_query(_select_key(field, field, xform), to_dict=False)
    return [float(i[0]) for i in result if i[0] is not None]


# pylint: disable=invalid-name
def get_form_submissions_grouped_by_field(xform, field, name=None, data_view=None):
    """Number of submissions grouped by field"""
    if not name:
        name = field

    query, params = _postgres_count_group(field, name, xform, data_view)

    return _execute_query(query, params)


# pylint: disable=invalid-name
def get_form_submissions_aggregated_by_select_one(
    xform, field, name=None, group_by=None, data_view=None
):
    """Number of submissions grouped and aggregated by select_one field"""
    if not name:
        name = field
    query, params = _postgres_aggregate_group_by(
        field, name, xform, group_by, data_view
    )

    return _execute_query(query, params)


# pylint: disable=invalid-name
def get_form_submissions_grouped_by_select_one(
    xform, field, group_by, name=None, data_view=None
):
    """Number of submissions disaggregated by select_one field"""
    if not name:
        name = field
    query, params = _postgres_count_group_field_n_group_by(
        field, name, xform, group_by, data_view
    )

    return _execute_query(query, params)


def get_numeric_fields(xform):
    """List of numeric field names for specified xform"""
    return _get_fields_of_type(xform, ["decimal", "integer"])


def is_date_field(xform, field):
    """Returns True if an XForm field is a date field."""
    return field in get_date_fields(xform)


def using_postgres():
    """Returns True if django.db.backends.postgresql is the DB engine in use"""
    return settings.DATABASES["default"]["ENGINE"] in [
        "django.db.backends.postgresql",
        "django.contrib.gis.db.backends.postgis",
    ]
