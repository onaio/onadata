import json
import six
from typing import Dict


def sort_from_mongo_sort_str(sort_str):
    sort_values = []
    if isinstance(sort_str, six.string_types):
        if sort_str.startswith('{'):
            sort_dict = json.loads(sort_str)
            for k, v in sort_dict.items():
                try:
                    v = int(v)
                except ValueError:
                    pass
                if v < 0:
                    k = u'-{}'.format(k)
                sort_values.append(k)
        else:
            sort_values.append(sort_str)

    return sort_values


def json_order_by(
        sort_list, none_json_fields: Dict = {}, model_name: str = ""):
    _list = []

    for field in sort_list:
        field_key = field.lstrip('-')
        _str = u" json->>%s"\
            if field_key not in none_json_fields.keys() else\
            f'"{model_name}"."{none_json_fields.get(field_key)}"'

        if field.startswith('-'):
            _str += u" DESC"
        else:
            _str += u" ASC"
        _list.append(_str)

    if len(_list) > 0:
        return u"ORDER BY {}".format(u",".join(_list))

    return u""


def json_order_by_params(sort_list, none_json_fields: Dict = {}):
    params = []

    for field in sort_list:
        field = field.lstrip('-')
        if field not in none_json_fields.keys():
            params.append(field.lstrip('-'))

    return params
