# -*- coding=utf-8 -*-
"""
Data utility functions.
"""
import six


def parse_int(num):
    """
    Parse integer from a string.
    """
    is_empty = isinstance(num, six.string_types) and len(num) == 0
    if is_empty:
        return None
    try:
        return num and int(num)
    except ValueError:
        pass
