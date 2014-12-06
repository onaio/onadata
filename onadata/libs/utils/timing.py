import time
import datetime
from itertools import chain
from django.utils import timezone
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.main.models.meta_data import MetaData
from django.contrib.auth.models import User


def print_time(func):
    """
    @print_time

    Put this decorator around a function to see how many seconds each
    call of this function takes to run.
    """
    def wrapped_func(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        seconds = end - start
        print "SECONDS:", seconds, func.__name__, kwargs
        return result
    return wrapped_func


def get_header_date_format(date_modified):
    format = "%a, %d %b %Y %H:%M:%S GMT"
    return date_modified.strftime(format)


def get_date(_object=None):
    if _object is None:
        return get_header_date_format(timezone.now())
    if isinstance(_object, Attachment):
        _object = _object.instance
    elif isinstance(_object, MetaData):
        _object = _object.xform
    elif isinstance(_object, User):
        _object = _object.profile

    _date = _object.date_modified

    return get_header_date_format(_date)


def last_modified_header(last_modified_date):
    return {'Last-Modified': last_modified_date}


def merge_dicts(*args):
    return dict(chain(*[d.items() for d in args]))


def calculate_duration(start_time, end_time):
    """
    This function calculates duration when given start and end times.
    An empty string is returned if either of the time formats does
    not match '_format' format else, the duration is returned
    """
    _format = "%Y-%m-%dT%H:%M:%S.%f+03:00"
    try:
        _start = datetime.datetime.strptime(start_time, _format)
        _end = datetime.datetime.strptime(end_time, _format)
    except ValueError:
        return ''

    duration = (_end - _start).total_seconds()

    return duration
