# -*- coding: utf-8 -*-
"""
String utility function str2bool - converts yes, true, t, 1 to True
else returns the argument value v.
"""


def str2bool(v):
    """
    String utility function str2bool - converts "yes", "true", "t", "1" to True
    else returns the argument value v.
    """
    return v.lower() in ("yes", "true", "t", "1") if isinstance(v, str) else v
