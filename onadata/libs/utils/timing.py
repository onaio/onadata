import time
from itertools import chain
from django.utils import timezone
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile


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


def get_date(_object=None, which_date=None):
    if _object is None:
        return get_header_date_format(timezone.now())
    if isinstance(_object, Attachment):
        _object = _object.instance
    elif isinstance(_object, UserProfile):
        _object = _object.user
    elif isinstance(_object, MetaData):
        _object = _object.xform

    if which_date == 'joined':
        _date = _object.date_joined
    elif which_date == 'modified':
        _date = _object.date_modified

    return get_header_date_format(_date)


def last_modified_header(last_modified_date):
    return {'Last-Modified': last_modified_date}


def merge_dicts(*args):
    return dict(chain(*[d.items() for d in args]))
