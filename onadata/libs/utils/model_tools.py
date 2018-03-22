# -*- coding=utf-8 -*-
"""
Model utility functions.
"""

import gc
import uuid


def generate_uuid_for_form():
    """
    Returns the UUID4 hex value.
    """
    return uuid.uuid4().hex


def set_uuid(obj):
    """
    Only give an object a new UUID if it does not have one.
    """
    if not obj.uuid:
        obj.uuid = generate_uuid_for_form()


def queryset_iterator(queryset, chunksize=100):
    '''
    Iterate over a Django Queryset.

    This method loads a maximum of chunksize (default: 100) rows in
    its memory at the same time while django normally would load all
    rows in its memory. Using the iterator() method only causes it to
    not preload all the classes.
    '''
    start = 0
    end = chunksize
    while start < queryset.count():
        for row in queryset[start:end]:
            yield row
        start += chunksize
        end += chunksize
        gc.collect()


def get_columns_with_hxl(survey_elements):
    '''
    Returns a dictionary whose keys are xform field names and values are
    `instance::hxl` values set on the xform
    :param include_hxl - boolean value
    :param survey_elements - survey elements of an xform
    return dictionary or None
    '''
    return survey_elements and {
        se.get('name'): val.get('hxl')
        for se in survey_elements
        for key, val in se.items()
        if key == 'instance' and val and 'hxl' in val
    }
