# -*- coding=utf-8 -*-
"""
The int_or_parse_error utility function.
"""
from rest_framework.exceptions import ParseError


def int_or_parse_error(value, error_string):
    """
    If `value` is not an int raise a parse error with `error_string`, which is
    a format string that takes one argument, the `value`.
    """
    try:
        int(value)
    except ValueError as exc:
        raise ParseError(error_string) from exc
