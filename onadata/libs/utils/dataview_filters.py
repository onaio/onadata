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


def get_field_lookup(column, filter_string):
    """
    Convert filter_string + column into a field lookup expression
    """
    return "json__" + column + filter_to_field_lookup(filter_string)


def get_filter_kwargs(filters):
    """
    Apply filters on a queryset
    """
    kwargs = {}
    if filters:
        for f in filters:
            value = f"{f['value']}"
            column = f["column"]
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
