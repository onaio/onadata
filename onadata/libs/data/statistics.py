import numpy as np
from onadata.apps.api.tools import DECIMAL_PRECISION
from onadata.libs.data.query import get_field_records, get_numeric_fields


def _chk_asarray(a, axis):
    if axis is None:
        a = np.ravel(a)
        outaxis = 0
    else:
        a = np.asarray(a)
        outaxis = axis
    return a, outaxis


def get_mean(values):
    return np.mean(values)


def get_median(values, axis=None):
    return np.median(values, axis)


def get_mode(values, axis=0):
    """
    Adapted from
    https://github.com/scipy/scipy/blob/master/scipy/stats/stats.py#L568
    """
    a, axis = _chk_asarray(values, axis)
    scores = np.unique(np.ravel(a))       # get ALL unique values
    testshape = list(a.shape)
    testshape[axis] = 1
    oldmostfreq = np.zeros(testshape)
    oldcounts = np.zeros(testshape)
    for score in scores:
        template = (a == score)
        counts = np.expand_dims(np.sum(template, axis), axis)
        mostfrequent = np.where(counts > oldcounts, score, oldmostfreq)
        oldcounts = np.maximum(counts, oldcounts)
        oldmostfreq = mostfrequent
    return mostfrequent, oldcounts


def get_median_for_field(field, xform):
    return np.median(get_field_records(field, xform))


def get_median_for_numeric_fields_in_form(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        median = get_median_for_field(field_name, xform)
        data.update({field_name: median})
    return data


def get_mean_for_field(field, xform):
    return np.mean(get_field_records(field, xform))


def get_mean_for_numeric_fields_in_form(xform, field):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mean = get_mean_for_field(field_name, xform)
        data.update({field_name: np.round(mean, DECIMAL_PRECISION)})
    return data


def get_mode_for_field(field, xform):
    a = np.array(get_field_records(field, xform))
    m, count = get_mode(a)
    return m


def get_mode_for_numeric_fields_in_form(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        mode = get_mode_for_field(field_name, xform)
        data.update({field_name: np.round(mode, DECIMAL_PRECISION)})
    return data


def get_min_max_range_for_field(field, xform):
    a = np.array(get_field_records(field, xform))
    _max = np.max(a)
    _min = np.min(a)
    _range = _max - _min
    return _min, _max, _range


def get_min_max_range(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        data[field_name] = {'max': _max, 'min': _min, 'range': _range}
    return data


def get_all_stats(xform, field=None):
    data = {}
    for field_name in [field] if field else get_numeric_fields(xform):
        _min, _max, _range = get_min_max_range_for_field(field_name, xform)
        mode = get_mode_for_field(field_name, xform)
        mean = get_mean_for_field(field_name, xform)
        median = get_median_for_field(field_name, xform)
        data[field_name] = {
            'mean': np.round(mean, DECIMAL_PRECISION),
            'median': median,
            'mode': np.round(mode, DECIMAL_PRECISION),
            'max': _max,
            'min': _min,
            'range': _range
        }
    return data
