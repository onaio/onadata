# -*- coding: utf-8 -*-
"""
Common helper functions
"""
from io import StringIO
import sys
import traceback
import uuid
from past.builtins import basestring
import six
from django.conf import settings
from django.core.mail import mail_admins
from django.utils.translation import ugettext as _
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
    Formats an exception and sends email to mail_admins.
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
            # fail silently
            pass
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
    assert filename_pos != -1

    return content_disposition[filename_pos + len('filename='):]


def get_response_content(response):
    """
    Gets HTTP content for the given a HTTP response object.

    Handles the case where a streaming_content is in the response.
    """
    contents = u''
    if response.streaming:
        actual_content = StringIO()
        for content in response.streaming_content:
            actual_content.write(content)
        contents = actual_content.getvalue()
        actual_content.close()
    else:
        contents = response.content

    return contents


def json_stream(data, json_string):
    """
    Generator function to stream JSON data
    """
    yield u"["
    try:
        data = data.__iter__()
        item = data.next()
        while item:
            try:
                next_item = data.next()
                yield json_string(item)
                yield ","
                item = next_item
            except StopIteration:
                yield json_string(item)
                break
    except AttributeError:
        pass
    finally:
        yield u"]"
