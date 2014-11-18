import time
from django.utils import timezone


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
        return timezone.now()
    if which_date == 'joined':
        return _object.date_joined
    elif which_date == 'modified':
        return _object.date_modified
