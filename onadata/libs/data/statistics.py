# -*- coding: utf-8 -*-
"""
Statistics utility functions.
"""
import numpy as np

from onadata.apps.api.tools import DECIMAL_PRECISION
from onadata.libs.data.query import get_field_records, get_numeric_fields


def _chk_asarray(a, axis):  # pylint: disable=invalid-name
    if axis is None:
        a = np.ravel(a)
        outaxis = 0
    else:
        a = np.asarray(a)
        outaxis = axis
    return a, outaxis


def get_mean(values):
    """Returns numpy.mean() of values."""
    return np.mean(values)


def get_median(values, axis=None):
    """Returns numpy.median() of values for the given axis"""
    return np.median(values, axis)


def get_mode(values, axis=0):
    """
    Adapted from
    https://github.com/scipy/scipy/blob/master/scipy/stats/stats.py#L568
    """
    a, axis = _chk_asarray(values, axis)  # pylint: disable=invalid-name
    scores = np.unique(np.ravel(a))  # get ALL unique values
    testshape = list(a.shape)
    testshape[axis] = 1
    oldmostfreq = np.zeros(testshape)
    oldcounts = np.zeros(testshape)
    for score in scores:
        template = a == score
        counts = np.expand_dims(np.sum(template, axis), axis)
        mostfrequent = np.where(counts > oldcounts, score, oldmostfreq)
        oldcounts = np.maximum(counts, oldcounts)
        oldmostfreq = mostfrequent
    return mostfrequent, oldcounts


def get_median_for_field(field, xform):
    """Returns numpy.median() of values in the given field."""
    return np.median(get_field_records(field, xform))


# pylint: disable=invalid-name
def get_median_for_numeric_fields_in_form(xform, field=None):
    """Get's numpy.median() of values in numeric fields.

    Returns a dict with the fields as key and the median as a value.
    """
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        median = get_median_for_field(field_name, xform)
        data.update({field_name: median})
    return data


def get_mean_for_field(field, xform):
    """Returns numpy.mean() of values in the given field."""
    return np.mean(get_field_records(field, xform))


# pylint: disable=invalid-name
def get_mean_for_numeric_fields_in_form(xform, field):
    """Get's numpy.mean() of values in numeric fields.

    Returns a dict with the fields as key and the mean as a value.
    """
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mean = get_mean_for_field(field_name, xform)
        data.update({field_name: np.round(mean, DECIMAL_PRECISION)})
    return data


def get_mode_for_field(field, xform):
    """Returns mode of values in the given field."""
    a = np.array(get_field_records(field, xform))  # pylint: disable=invalid-name
    m, _count = get_mode(a)  # pylint: disable=invalid-name
    return m


# pylint: disable=invalid-name
def get_mode_for_numeric_fields_in_form(xform, field=None):
    """Get's mode of values in numeric fields.

    Returns a dict with the fields as key and the mode as a value.
    """
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mode = get_mode_for_field(field_name, xform)
        data.update({field_name: np.round(mode, DECIMAL_PRECISION)})
    return data


def get_min_max_range_for_field(field, xform):
    """Returns min, max, range of values in the given field."""
    a = np.array(get_field_records(field, xform))  # pylint: disable=invalid-name
    _max = np.max(a)
    _min = np.min(a)
    _range = _max - _min
    return _min, _max, _range


def get_min_max_range(xform, field=None):
    """Get's min, max, range of values in numeric fields.

    Returns a dict with the fields as key and the min, max, range as a value.
    """
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        data[field_name] = {"max": _max, "min": _min, "range": _range}
    return data


def get_all_stats(xform, field=None):
    """Get's mean, median, mode, min, max, range of values in numeric fields.

    Returns a dict with the fields as key and the mean, median, mode, min, max,
    range as a value.
    """
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        mode = get_mode_for_field(field_name, xform)
        mean = get_mean_for_field(field_name, xform)
        median = get_median_for_field(field_name, xform)
        data[field_name] = {
            "mean": np.round(mean, DECIMAL_PRECISION),
            "median": median,
            "mode": np.round(mode, DECIMAL_PRECISION),
            "max": _max,
            "min": _min,
            "range": _range,
        }
    return data
