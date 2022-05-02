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
    return None


# source from deprecated module distutils/util.py
def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    if val in ("n", "no", "f", "false", "off", "0"):
        return 0
    raise ValueError(f"invalid truth value {val}")
