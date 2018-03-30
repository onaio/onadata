import datetime
import six

from django.utils import timezone


def get_header_date_format(date_modified):
    format = "%a, %d %b %Y %H:%M:%S GMT"
    return date_modified.strftime(format)


def get_date(_object=None):
    if hasattr(_object, "date_modified"):
        _date = _object.date_modified
    elif hasattr(_object, "instance"):
        _date = _object.instance.date_modified
    elif hasattr(_object, "xform"):
        _date = _object.xform.date_modified
    elif hasattr(_object, "profile"):
        _date = _object.profile.date_modified
    elif isinstance(_object, dict):
        # most likely an instance json, use _submission_time
        _date = _object.get('_submission_time')
        if isinstance(_date, six.string_types):
            _date = datetime.datetime.strptime(_date[:19], '%Y-%m-%dT%H:%M:%S')
    else:
        # default value to avoid the UnboundLocalError
        _date = timezone.now()

    return get_header_date_format(_date)


def last_modified_header(last_modified_date):
    return {'Last-Modified': last_modified_date}


def calculate_duration(start_time, end_time):
    """
    This function calculates duration when given start and end times.
    An empty string is returned if either of the time formats does
    not match '_format' format else, the duration is returned
    """
    _format = "%Y-%m-%dT%H:%M:%S"
    try:
        _start = datetime.datetime.strptime(start_time[:19], _format)
        _end = datetime.datetime.strptime(end_time[:19], _format)
    except (TypeError, ValueError):
        return ''

    duration = (_end - _start).total_seconds()

    return duration
