# -*- coding: utf-8 -*-
"""
Common helper functions
"""
from __future__ import unicode_literals

import logging
import math
import sys
import time
import traceback
import uuid
from io import BytesIO
from past.builtins import basestring

from django.conf import settings
from django.core.mail import mail_admins
from django.db import OperationalError
from django.utils.translation import ugettext as _

import six
from raven.contrib.django.raven_compat.models import client

TRUE_VALUES = ['TRUE', 'T', '1', 1]


def str_to_bool(str_var):
    """
    Return boolean True or False if string s represents a boolean value
    """
    # no need to convert boolean values otherwise it will always be false
    if isinstance(str_var, bool):
        return str_var

    __ = str_var.upper() if isinstance(str_var, six.string_types) else str_var

    return __ in TRUE_VALUES


def get_boolean_value(str_var, default=None):
    """
    Converts a string into boolean
    """
    if isinstance(str_var, basestring) and \
            str_var.lower() in ['true', 'false']:
        return str_to_bool(str_var)

    return str_var if default else False


def get_uuid():
    '''
    Return UUID4 hex value
    '''
    return uuid.uuid4().hex


def report_exception(subject, info, exc_info=None):
    """
    Formats an exception then posts it to sentry and if not in debug or
    testing sends email to mail_admins.
    """
    # Add hostname to subject mail
    subject = "{0} - {1}".format(subject, settings.HOSTNAME)

    if exc_info:
        cls, err = exc_info[:2]
        message = _(u"Exception in request:"
                    u" %(class)s: %(error)s")\
            % {'class': cls.__name__, 'error': err}
        message += u"".join(traceback.format_exception(*exc_info))

        # send to sentry
        try:
            client.captureException(exc_info)
        except Exception:  # pylint: disable=broad-except
            logging.exception(_(u'Sending to Sentry failed.'))
    else:
        message = u"%s" % info

    if settings.DEBUG or settings.TESTING_MODE:
        sys.stdout.write("Subject: %s\n" % subject)
        sys.stdout.write("Message: %s\n" % message)
    else:
        mail_admins(subject=subject, message=message)


def filename_from_disposition(content_disposition):
    """
    Gets a filename from the given content disposition header.
    """
    filename_pos = content_disposition.index('filename=')

    if filename_pos == -1:
        raise Exception('"filename=" not found in content disposition file')

    return content_disposition[filename_pos + len('filename='):]


def get_response_content(response, decode=True):
    """
    Gets HTTP content for the given a HTTP response object.

    Handles the case where a streaming_content is in the response.

    :param response: The response to extract content from.
    :param decode: If true decode as utf-8, default True.
    """
    contents = ''
    if response.streaming:
        actual_content = BytesIO()
        for content in response.streaming_content:
            actual_content.write(content)
        contents = actual_content.getvalue()
        actual_content.close()
    else:
        contents = response.content

    if decode:
        return contents.decode('utf-8')
    else:
        return contents


def json_stream(data, json_string):
    """
    Generator function to stream JSON data
    """
    yield '['
    try:
        data = data.__iter__()
        item = next(data)
        while item:
            try:
                next_item = next(data)
                yield json_string(item)
                yield ','
                item = next_item
            except StopIteration:
                yield json_string(item)
                break
    except AttributeError:
        pass
    finally:
        yield ']'


def retry(tries, delay=3, backoff=2):
    """
    Adapted from code found here:
        http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    Retries a function or method until it returns True.

    :param delay: sets the initial delay in seconds, and *backoff* sets the
    factor by which the delay should lengthen after each failure.
    :param backoff: must be greater than 1, or else it isn't really a backoff.
    :param tries: must be at least 0, and *delay* greater than 0.
    """

    if backoff <= 1:  # pragma: no cover
        raise ValueError("backoff must be greater than 1")

    tries = math.floor(tries)
    if tries < 0:  # pragma: no cover
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:  # pragma: no cover
        raise ValueError("delay must be greater than 0")

    def decorator_retry(func):
        def function_retry(self, *args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 0:
                try:
                    result = func(self, *args, **kwargs)
                except OperationalError:
                    mtries -= 1
                    time.sleep(mdelay)
                    mdelay *= backoff
                else:
                    return result
            # Last ditch effort run against master database
            if len(getattr(settings, 'SLAVE_DATABASES', [])):
                from multidb.pinning import use_master
                with use_master:
                    return func(self, *args, **kwargs)

            # last attempt, exception raised from function is propagated
            return func(self, *args, **kwargs)

        return function_retry
    return decorator_retry


def merge_dicts(*dict_args):
    """ Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}

    for dictionary in dict_args:
        result.update(dictionary)

    return result


def cmp_to_key(mycmp):
    """ Convert a cmp= function into a key= function
    """
    class K(object):
        def __init__(self, obj, *args):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K
