import json

def get_values_matching_key(doc, key):
    def _get_values(doc, key):
        if doc is not None:
            if key in doc:
                yield doc[key]

            for k, v in doc.items():
                if isinstance(v, dict):
                    for item in _get_values(v, key):
                        yield item
                elif isinstance(v, list):
                    for i in v:
                        for j in _get_values(i, key):
                            yield j

    return _get_values(doc, key)


def list_to_dict(items, value):
    key = items.pop()

    result = {}
    bracket_index = key.find('[')
    if bracket_index > 0:
        value = [value]

    result[key] = value

    if len(items):
        result = list_to_dict(items, result)

    return result


def merge_list_of_dicts(list_of_dicts):
    result = {}

    for d in list_of_dicts:
        for k, v in d.items():
            if isinstance(v, list):
                rs = merge_list_of_dicts(result[k] + v if k in result else v)
                result[k] = rs if isinstance(rs, list) else [rs]
            else:
                if k in result:
                    if isinstance(v, dict):
                        result[k] = merge_list_of_dicts([result[k], v])
                    else:
                        result = [result, d]
                else:
                    result[k] = v

    return result


def remove_indices_from_dict(obj):
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


def csv_dict_to_nested_dict(a):
    results = []

    for key in a.keys():
        result = {}
        value = a[key]
        split_keys = key.split('/')

        if len(split_keys) == 1:
            result[key] = value
        else:
            result = list_to_dict(split_keys, value)

        results.append(result)

    merged_dict = merge_list_of_dicts(results)

    return remove_indices_from_dict(merged_dict)


def dict_lists2strings(d):
    """Convert lists in a dict to joined strings.

    :param d: The dict to convert.
    :returns: The converted dict."""
    for k, v in d.items():
        if isinstance(v, list) and all([isinstance(e, basestring) for e in v]):
            d[k] = ' '.join(v)
        elif isinstance(v, dict):
            d[k] = dict_lists2strings(v)

    return d


def dict_paths2dict(d):
    result = {}

    for k, v in d.items():
        if k.find('/') > 0:
            parts = k.split('/')
            if len(parts) > 1:
                k = parts[0]
                for p in parts[1:]:
                    v = {p: v}

        result[k] = v

    return result


def query_list_to_dict(query_list):
    data_list = json.loads(query_list)
    data_dict = dict()
    for value in data_list:
        data_dict[value['label']] = value['text']

    return data_dict
