from __future__ import unicode_literals

import base64
import re
from functools import reduce


key_whitelist = ['$or', '$and', '$exists', '$in', '$gt', '$gte',
                 '$lt', '$lte', '$regex', '$options', '$all']
b64dollar = base64.b64encode(b'$').decode('utf-8')
b64dot = base64.b64encode(b'.').decode('utf-8')
re_b64dollar = re.compile(r'^%s' % b64dollar)
re_b64dot = re.compile(r'%s' % b64dot)
re_dollar = re.compile(r'^\$')
re_dot = re.compile(r'\.')


def _pattern_transform(key, transform_list):
    return reduce(lambda s, c: c[0].sub(c[1], s), transform_list, key)


def _decode_from_mongo(key):
    return _pattern_transform(key, [(re_b64dollar, '$'), (re_b64dot, '.')])


def _encode_for_mongo(key):
    return _pattern_transform(key, [(re_dollar, b64dollar), (re_dot, b64dot)])


def _is_invalid_for_mongo(key):
    return key not in\
        key_whitelist and (key.startswith('$') or key.count('.') > 0)
