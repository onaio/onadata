# -*- coding: utf-8 -*-
"""
Dict utility functions module.
"""
import json


def get_values_matching_key(doc, key):
    """
    Returns iterator of values in 'doc' with the matching 'key'.
    """

    def _get_values(doc, key):
        # pylint: disable=too-many-nested-blocks
        if doc is not None:
            if key in doc:
                yield doc[key]

            for doc_item in doc.items():
                value = doc_item[1]
                if isinstance(value, dict):
                    yield from _get_values(value, key)
                elif isinstance(value, list):
                    for item_i in value:
                        if isinstance(item_i, (dict, list)):
                            try:
                                yield from _get_values(item_i, key)
                            except StopIteration:
                                continue
                        elif item_i == key:
                            yield item_i

    return _get_values(doc, key)


def list_to_dict(items, value):
    """
    Converts a list into a dict.
    """
    key = items.pop()

    result = {}
    bracket_index = key.find("[")
    if bracket_index > 0:
        value = [value]

    result[key] = value

    if items:
        result = list_to_dict(items, result)

    return result


def merge_list_of_dicts(list_of_dicts, override_keys: list = None):
    """
    Merges a list of dicts to return one dict.
    """
    result = {}

    # pylint: disable=too-many-nested-blocks
    for row in list_of_dicts:
        for key, value in row.items():
            if isinstance(value, list):
                item_z = merge_list_of_dicts(
                    result[key] + value if key in result else value,
                    override_keys=override_keys,
                )
                result[key] = item_z if isinstance(item_z, list) else [item_z]
            else:
                if key in result:
                    if isinstance(value, dict):
                        try:
                            result[key] = merge_list_of_dicts(
                                [result[key], value], override_keys=override_keys
                            )
                        except AttributeError as error:
                            # If the key is within the override_keys
                            # (Is a select_multiple question) We make
                            # the assumption that the dict values are
                            # more accurate as they usually mean that
                            # the select_multiple has been split into
                            # separate columns for each choice
                            if (
                                override_keys
                                and isinstance(result[key], str)
                                and key in override_keys
                            ):
                                result[key] = {}
                                result[key] = merge_list_of_dicts(
                                    [result[key], value], override_keys=override_keys
                                )
                            else:
                                raise error
                    else:
                        result = [result, row]
                else:
                    result[key] = value

    return result


def remove_indices_from_dict(obj):
    """
    Removes indices from a obj dict.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Expecting a dict, found: {type(obj)}")

    result = {}
    for key, val in obj.items():
        bracket_index = key.find("[")
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


def csv_dict_to_nested_dict(csv_dict, select_multiples=None):
    """
    Converts a CSV dict to nested dicts.
    """
    results = []

    for key in list(csv_dict):
        result = {}
        value = csv_dict[key]
        split_keys = key.split("/")

        if len(split_keys) == 1:
            result[key] = value
        else:
            result = list_to_dict(split_keys, value)

        results.append(result)

    merged_dict = merge_list_of_dicts(results, select_multiples)

    return remove_indices_from_dict(merged_dict)


def dict_lists2strings(adict):
    """
    Convert lists in a dict to joined strings.

    :param d: The dict to convert.
    :returns: The converted dict."""
    for key, value in adict.items():
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            adict[key] = " ".join(value)
        elif isinstance(value, dict):
            adict[key] = dict_lists2strings(value)

    return adict


def dict_paths2dict(adict):
    """
    Turns a dict with '/' in keys to a nested dict.
    """
    result = {}

    for key, value in adict.items():
        if key.find("/") > 0:
            parts = key.split("/")
            if len(parts) > 1:
                key = parts[0]
                for part in parts[1:]:
                    value = {part: value}

        result[key] = value

    return result


def query_list_to_dict(query_list_str):
    """
    Returns a 'label' and 'text' from a Rapidpro values JSON string as a dict.
    """
    data_list = json.loads(query_list_str)
    data_dict = {}
    for value in data_list:
        data_dict[value["label"]] = value["text"]

    return data_dict


def floip_response_headers_dict(data, xform_headers):
    """
    Returns a dict from matching xform headers and floip responses.
    """
    headers = [i.split("/")[-1] for i in xform_headers]
    data = [i[4] for i in data]
    flow_dict = dict(zip(headers, data))

    return flow_dict
