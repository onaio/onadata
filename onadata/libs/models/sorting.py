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
            for key, value in sort_dict.items():
                try:
                    value = int(value)
                except ValueError:
                    pass
                if value < 0:
                    key = f"-{key}"
                sort_values.append(key)
        else:
            sort_values.append(sort_str)

    return sort_values


def json_order_by(sort_list, none_json_fields: Dict = None, model_name: str = ""):
    """Returns SQL ORDER BY string portion based on JSON input."""
    _list = []
    if none_json_fields is None:
        none_json_fields = {}

    for field in sort_list:
        field_key = field.lstrip("-")
        _str = (
            " json->>%s"
            if field_key not in none_json_fields
            else f'"{model_name}"."{none_json_fields.get(field_key)}"'
        )

        if field.startswith("-"):
            _str += " DESC"
        else:
            _str += " ASC"
        _list.append(_str)

    if len(_list) > 0:
        return f'ORDER BY {",".join(_list)}'

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
