# -*- coding: utf-8 -*-
"""
String utility function str2bool - converts yes, true, t, 1 to True
else returns the argument value v.
"""


def str2bool(value):
    """
    String utility function str2bool - converts "yes", "true", "t", "1" to True
    else returns the argument value v.
    """
    return (
        value.lower() in ("yes", "true", "t", "1") if isinstance(value, str) else value
    )
