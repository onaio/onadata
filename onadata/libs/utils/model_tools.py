# -*- coding: utf-8 -*-
"""
Model utility functions.
"""

from onadata.libs.utils.common_tools import get_uuid


def set_uuid(obj):
    """
    Only give an object a new UUID if it does not have one.
    """
    if not obj.uuid:
        obj.uuid = get_uuid()


def queryset_iterator(queryset, chunksize=100):
    """
    Iterate over a Django Queryset.

    This method loads a maximum of chunksize (default: 100) rows in
    its memory at the same time while django normally would load all
    rows in its memory. Using the iterator() method only causes it to
    not preload all the classes.

    See https://docs.djangoproject.com/en/2.1/ref/models/querysets/#iterator
    """

    return queryset.iterator(chunk_size=chunksize)


def get_columns_with_hxl(survey_elements):
    """
    Returns a dictionary whose keys are xform field names and values are
    `instance::hxl` values set on the xform
    :param include_hxl - boolean value
    :param survey_elements - survey elements of an xform
    return dictionary or None
    """
    return survey_elements and {
        se.name: se.instance["hxl"]
        for se in survey_elements
        if se.instance and "hxl" in se.instance
    }
