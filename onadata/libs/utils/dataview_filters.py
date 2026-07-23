# -*- coding: utf-8 -*-
"""
Helpers for translating DataView ``query`` JSON into Django ORM filters.

Lives outside the viewset so non-viewset callers (e.g. bbox computation,
shared filter classes) can reuse the same semantics without pulling in the
viewset module and creating a cyclic import.
"""


def filter_to_field_lookup(filter_string):
    """
    Converts a =, < or > to a django field lookup
    """
    if filter_string == "=":
        return "__iexact"
    if filter_string == "<":
        return "__lt"
    return "__gt"


def is_safe_column(column):
    """Return ``True`` if ``column`` is a safe DataView filter reference.

    A safe column is a string that does not contain the Django ORM lookup
    separator ``__``. Nested form fields use ``/`` as their path separator, so
    ``__`` never appears in a legitimate column; left unchecked it would be
    interpreted as a relation/lookup traversal by ``filter(**kwargs)`` via
    ``get_field_lookup``.
    """
    return isinstance(column, str) and "__" not in column


def get_field_lookup(column, filter_string):
    """
    Convert filter_string + column into a field lookup expression
    """
    return "json__" + column + filter_to_field_lookup(filter_string)


def get_filter_kwargs(filters):
    """
    Build ORM filter kwargs from DataView ``query`` filters.

    Columns that are not safe json key references (non-strings, or values
    containing the ``__`` lookup separator) are dropped rather than applied.
    The serializer rejects these on write, but DataViews created directly or
    stored before that guard must not reach ``filter(**kwargs)`` with a column
    that escapes the json key boundary.
    """
    kwargs = {}
    if filters:
        for f in filters:
            column = f["column"]
            if not is_safe_column(column):
                continue
            value = f"{f['value']}"
            filter_kwargs = {get_field_lookup(column, f["filter"]): value}
            kwargs = {**kwargs, **filter_kwargs}
    return kwargs


def apply_filters(instance_qs, filters):
    """
    Apply filters on a queryset
    """
    if filters:
        return instance_qs.filter(**get_filter_kwargs(filters))
    return instance_qs
