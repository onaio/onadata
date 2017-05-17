import json
import six
import datetime

from onadata.libs.utils.common_tags import MONGO_STRFTIME

KNOWN_DATES = ['_submission_time']
NONE_JSON_FIELDS = {
    '_submission_time': 'date_created',
    '_id': 'id',
    '_version': 'version'
}


def _json_sql_str(key, known_integers=[], known_dates=[]):
    _json_str = u"json->>%s"

    if key in known_integers:
        _json_str = u"CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = u"CAST(json->>%s AS TIMESTAMP)"

    return _json_str


def _parse_where(query, known_integers, or_where, or_params):
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
    for field_key, field_value in query.iteritems():
        if isinstance(field_value, dict):
            if field_key in NONE_JSON_FIELDS:
                json_str = NONE_JSON_FIELDS.get(field_key)
            else:
                json_str = _json_sql_str(
                    field_key, known_integers, KNOWN_DATES)
            for key, value in field_value.iteritems():
                _v = None
                if key in OPERANDS:
                    where.append(
                        u' '.join([json_str, OPERANDS.get(key), u'%s'])
                    )
                _v = value
                if field_key in KNOWN_DATES:
                    _v = datetime.datetime.strptime(
                        _v[:19], MONGO_STRFTIME)
                if field_key in NONE_JSON_FIELDS:
                    where_params.extend([unicode(_v)])
                else:
                    where_params.extend((field_key, unicode(_v)))
        else:
            if field_key in NONE_JSON_FIELDS:
                where.append("{} = %s".format(NONE_JSON_FIELDS[field_key]))
                where_params.extend([unicode(field_value)])
            else:
                where.append(u"json->>%s = %s")
                where_params.extend((field_key, unicode(field_value)))

    return where + or_where, where_params + or_params


def get_where_clause(query, form_integer_fields=[]):
    known_integers = ['_id'] + form_integer_fields
    where = []
    where_params = []

    try:
        if query and isinstance(query, six.string_types):
            query = json.loads(query)
            or_where = []
            or_params = []
            if isinstance(query, list):
                query = query[0]

            if '$or' in query.keys():
                or_dict = query.pop('$or')
                for l in or_dict:
                    or_where.extend([u"json->>%s = %s" for i in l.items()])
                    [or_params.extend(i) for i in l.items()]

                or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

            where, where_params = _parse_where(query, known_integers,
                                               or_where, or_params)

    except (ValueError, AttributeError) as e:
        if query and isinstance(query, six.string_types) and \
                query.startswith('{'):
            raise e
        # cast query param to text
        where = [u"json::text ~* cast(%s as text)"]
        where_params = [query]

    return where, where_params
