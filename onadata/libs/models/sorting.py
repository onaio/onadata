# -*- coding: utf-8 -*-
"""
Sorting utility functions.
"""
import json
from typing import Dict

import six


def sort_from_mongo_sort_str(sort_str):
    """Create a sort query list based on MongoDB sort string input."""
    sort_values = []
    if isinstance(sort_str, six.string_types):
        if sort_str.startswith("{"):
            sort_dict = json.loads(sort_str)
            for k, v in sort_dict.items():
                try:
                    v = int(v)
                except ValueError:
                    pass
                if v < 0:
                    k = f"-{k}"
                sort_values.append(k)
        else:
            sort_values.append(sort_str)

    return sort_values


def json_order_by(sort_list, none_json_fields: Dict = None, model_name: str = ""):
    """Returns SQL ORDER BY string portion based on JSON input."""
    _list = []

    for field in sort_list:
        field_key = field.lstrip("-")
        _str = (
            " json->>%s"
            if none_json_fields and field_key not in none_json_fields.keys()
            else f'"{model_name}"."{none_json_fields.get(field_key)}"'
        )

        if field.startswith("-"):
            _str += " DESC"
        else:
            _str += " ASC"
        _list.append(_str)

    if len(_list) > 0:
        return f'ORDER BY {"".join(_list)}'

    return ""


def json_order_by_params(sort_list, none_json_fields: Dict = None):
    """Creates the ORDER BY parameters list from JSON input."""
    params = []
    if none_json_fields is None:
        none_json_fields = {}

    for field in sort_list:
        field = field.lstrip("-")
        if field not in none_json_fields:
            params.append(field.lstrip("-"))

    return params
