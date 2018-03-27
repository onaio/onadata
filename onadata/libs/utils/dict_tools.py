# -*- coding=utf-8 -*-
"""
Dict utility functions module.
"""
import json

from past.builtins import basestring


def get_values_matching_key(doc, key):
    """
    Returns iterator of values in 'doc' with the matching 'key'.
    """

    def _get_values(doc, key):
        if doc is not None:
            if key in doc:
                yield doc[key]

            for z in doc.items():
                v = z[1]
                if isinstance(v, dict):
                    for item in _get_values(v, key):
                        yield item
                elif isinstance(v, list):
                    for i in v:
                        for j in _get_values(i, key):
                            yield j

    return _get_values(doc, key)


def list_to_dict(items, value):
    """
    Converts a list into a dict.
    """
    key = items.pop()

    result = {}
    bracket_index = key.find('[')
    if bracket_index > 0:
        value = [value]

    result[key] = value

    if items:
        result = list_to_dict(items, result)

    return result


def merge_list_of_dicts(list_of_dicts):
    """
    Merges a list of dicts to return one dict.
    """
    result = {}

    for row in list_of_dicts:
        for k, v in row.items():
            if isinstance(v, list):
                z = merge_list_of_dicts(result[k] + v if k in result else v)
                result[k] = z if isinstance(z, list) else [z]
            else:
                if k in result:
                    if isinstance(v, dict):
                        result[k] = merge_list_of_dicts([result[k], v])
                    else:
                        result = [result, row]
                else:
                    result[k] = v

    return result


def remove_indices_from_dict(obj):
    """
    Removes indices from a obj dict.
    """
    if not isinstance(obj, dict):
        raise ValueError(u"Expecting a dict, found: {}".format(type(obj)))

    result = {}
    for key, val in obj.items():
        bracket_index = key.find('[')
        key = key[:bracket_index] if bracket_index > -1 else key
        val = remove_indices_from_dict(val) if isinstance(val, dict) else val
        if isinstance(val, list):
            _val = []
            for row in val:
                if isinstance(row, dict):
                    row = remove_indices_from_dict(row)
                _val.append(row)
            val = _val
        if key in result:
            result[key].extend(val)
        else:
            result[key] = val

    return result


def csv_dict_to_nested_dict(csv_dict):
    """
    Converts a CSV dict to nested dicts.
    """
    results = []

    for key in list(csv_dict):
        result = {}
        value = csv_dict[key]
        split_keys = key.split('/')

        if len(split_keys) == 1:
            result[key] = value
        else:
            result = list_to_dict(split_keys, value)

        results.append(result)

    merged_dict = merge_list_of_dicts(results)

    return remove_indices_from_dict(merged_dict)


def dict_lists2strings(adict):
    """
    Convert lists in a dict to joined strings.

    :param d: The dict to convert.
    :returns: The converted dict."""
    for k, v in adict.items():
        if isinstance(v, list) and all([isinstance(e, basestring) for e in v]):
            adict[k] = ' '.join(v)
        elif isinstance(v, dict):
            adict[k] = dict_lists2strings(v)

    return adict


def dict_paths2dict(adict):
    """
    Turns a dict with '/' in keys to a nested dict.
    """
    result = {}

    for k, v in adict.items():
        if k.find('/') > 0:
            parts = k.split('/')
            if len(parts) > 1:
                k = parts[0]
                for part in parts[1:]:
                    v = {part: v}

        result[k] = v

    return result


def query_list_to_dict(query_list_str):
    """
    Returns a 'label' and 'text' from a Rapidpro values JSON string as a dict.
    """
    data_list = json.loads(query_list_str)
    data_dict = dict()
    for value in data_list:
        data_dict[value['label']] = value['text']

    return data_dict


def floip_response_headers_dict(data, xform_headers):
    """
    Returns a dict from matching xform headers and floip responses.
    """
    headers = [i.split('/')[-1] for i in xform_headers]
    data = [i[4] for i in data]
    flow_dict = dict(zip(headers, data))

    return flow_dict
