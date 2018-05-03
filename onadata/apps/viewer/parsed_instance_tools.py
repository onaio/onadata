import json
import six
import datetime
from builtins import str as text
from future.utils import iteritems

from onadata.libs.utils.common_tags import MONGO_STRFTIME, DATE_FORMAT

KNOWN_DATES = ['_submission_time']
NONE_JSON_FIELDS = {
    '_submission_time': 'date_created',
    '_id': 'id',
    '_version': 'version'
}


def _json_sql_str(key, known_integers=None, known_dates=None,
                  known_decimals=None):
    if known_integers is None:
        known_integers = []
    if known_dates is None:
        known_dates = []
    if known_decimals is None:
        known_decimals = []
    _json_str = u"json->>%s"

    if key in known_integers:
        _json_str = u"CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = u"CAST(json->>%s AS TIMESTAMP)"
    elif key in known_decimals:
        _json_str = u"CAST(json->>%s AS DECIMAL)"

    return _json_str


def _parse_where(query, known_integers, known_decimals, or_where, or_params):
    # using a dictionary here just incase we will need to filter using
    # other table columns
    where, where_params = [], []
    OPERANDS = {
        '$gt': '>',
        '$gte': '>=',
        '$lt': '<',
        '$lte': '<=',
        '$i': '~*'
    }
    for (field_key, field_value) in iteritems(query):
        if isinstance(field_value, dict):
            if field_key in NONE_JSON_FIELDS:
                json_str = NONE_JSON_FIELDS.get(field_key)
            else:
                json_str = _json_sql_str(
                    field_key, known_integers, KNOWN_DATES, known_decimals)
            for (key, value) in iteritems(field_value):
                _v = None
                if key in OPERANDS:
                    where.append(
                        u' '.join([json_str, OPERANDS.get(key), u'%s'])
                    )
                _v = value
                if field_key in KNOWN_DATES:
                    raw_date = value
                    for date_format in (MONGO_STRFTIME, DATE_FORMAT):
                        try:
                            _v = datetime.datetime.strptime(raw_date[:19],
                                                            date_format)
                        except ValueError:
                            pass
                if field_key in NONE_JSON_FIELDS:
                    where_params.extend([text(_v)])
                else:
                    where_params.extend((field_key, text(_v)))
        else:
            if field_key in NONE_JSON_FIELDS:
                where.append("{} = %s".format(NONE_JSON_FIELDS[field_key]))
                where_params.extend([text(field_value)])
            else:
                where.append(u"json->>%s = %s")
                where_params.extend((field_key, text(field_value)))

    return where + or_where, where_params + or_params


def get_where_clause(query, form_integer_fields=None,
                     form_decimal_fields=None):
    if form_integer_fields is None:
        form_integer_fields = []
    if form_decimal_fields is None:
        form_decimal_fields = []
    known_integers = ['_id'] + form_integer_fields
    known_decimals = form_decimal_fields
    where = []
    where_params = []

    try:
        if query and isinstance(query, (dict, six.string_types)):
            query = query if isinstance(query, dict) else json.loads(query)
            or_where = []
            or_params = []
            if isinstance(query, list):
                query = query[0]

            if isinstance(query, dict) and '$or' in list(query):
                or_dict = query.pop('$or')
                for l in or_dict:
                    or_where.extend([u"json->>%s = %s" for i in iteritems(l)])
                    for i in iteritems(l):
                        or_params.extend(i)

                or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

            where, where_params = _parse_where(query, known_integers,
                                               known_decimals, or_where,
                                               or_params)

    except (ValueError, AttributeError) as e:
        if query and isinstance(query, six.string_types) and \
                query.startswith('{'):
            raise e
        # cast query param to text
        where = [u"json::text ~* cast(%s as text)"]
        where_params = [query]

    return where, where_params
