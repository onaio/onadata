import re

from rest_framework.exceptions import ParseError
from django.utils.html import conditional_escape
from urllib.parse import quote


def int_or_parse_error(value, error_string):
    """
    If `value` is not an int raise a parse error with `error_string`, which is
    a format string that takes one argument, the `value`.
    """
    try:
        int(value)
    except ValueError:
        value = conditional_escape(value)
        if re.findall(r"://([\w\-\.]+)(:(\d+))?", value):
            value = quote(value)
        raise ParseError(error_string % value)
