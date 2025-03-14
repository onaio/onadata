# -*- coding: utf-8 -*-
"""
Common helper functions
"""

from __future__ import unicode_literals

import math
import sys
import time
import traceback
import uuid
from io import BytesIO

from django.conf import settings
from django.core.mail import mail_admins
from django.db import OperationalError
from django.utils.translation import gettext as _

import sentry_sdk
import six
from celery import current_task

from onadata.libs.utils.common_tags import ATTACHMENTS

DEFAULT_UPDATE_BATCH = 100
TRUE_VALUES = ["TRUE", "T", "1", 1]


class FilenameMissing(Exception):
    """Custom Exception for a missing filename."""


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
    if isinstance(str_var, str) and str_var.lower() in ["true", "false"]:
        return str_to_bool(str_var)

    return str_var if default else False


def get_uuid(hex_only: bool = True):
    """
    Return UUID4 hex value
    """
    return uuid.uuid4().hex if hex_only else str(uuid.uuid4())


def report_exception(subject, info, exc_info=None):
    """
    Formats an exception then posts it to sentry and if not in debug or
    testing sends email to mail_admins.
    """
    # Add hostname to subject mail
    subject = f"{subject} - {settings.HOSTNAME}"

    if exc_info:
        cls, err = exc_info[:2]
        message = _(f"Exception in request: {cls.__name__}: {err}")
        message += "".join(traceback.format_exception(*exc_info))

        # send to sentry
        sentry_sdk.capture_exception(exc_info)
    else:
        message = f"{info}"
        sentry_sdk.capture_message(f"{subject}: {info}")

    if settings.DEBUG or settings.TESTING_MODE:
        sys.stdout.write(f"Subject: {subject}\n")
        sys.stdout.write(f"Message: {message}\n")
    else:
        mail_admins(subject=subject, message=message)


def filename_from_disposition(content_disposition):
    """
    Gets a filename from the given content disposition header.
    """
    filename_pos = content_disposition.index("filename=")

    if filename_pos == -1:
        raise FilenameMissing('"filename=" not found in content disposition file')

    return content_disposition[filename_pos + len("filename=") :]


def get_response_content(response, decode=True):
    """
    Gets HTTP content for the given a HTTP response object.

    Handles the case where a streaming_content is in the response.

    :param response: The response to extract content from.
    :param decode: If true decode as utf-8, default True.
    """
    contents = ""
    if response.streaming:
        actual_content = BytesIO()
        for content in response.streaming_content:
            actual_content.write(content)
        contents = actual_content.getvalue()
        actual_content.close()
    else:
        contents = response.content

    if decode:
        return contents.decode("utf-8")
    return contents


def json_stream(data, json_string):
    """
    Generator function to stream JSON data
    """
    yield "["
    try:
        data = iter(data)
        item = next(data)
        while item:
            try:
                next_item = next(data)
                yield json_string(item)
                yield ","
                item = next_item
            except StopIteration:
                yield json_string(item)
                break
    except (AttributeError, StopIteration):
        pass
    finally:
        yield "]"


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
            if len(getattr(settings, "SLAVE_DATABASES", [])):
                # pylint: disable=import-outside-toplevel
                from multidb.pinning import use_master

                with use_master:
                    return func(self, *args, **kwargs)

            # last attempt, exception raised from function is propagated
            return func(self, *args, **kwargs)

        return function_retry

    return decorator_retry


def merge_dicts(*dict_args):
    """Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}

    for dictionary in dict_args:
        result.update(dictionary)

    return result


def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function"""

    class ComparatorClass:
        """A class that implements comparison methods."""

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

    return ComparatorClass


def current_site_url(path, host):
    """
    Returns fully qualified URL (no trailing slash) for the current site.
    :param path
    :return: complete url
    """
    protocol = getattr(settings, "ONA_SITE_PROTOCOL", "http")
    port = getattr(settings, "ONA_SITE_PORT", "")
    url = f"{protocol}://{host}"
    if port:
        url += f":{port}"
    if path:
        url += f"{path}"

    return url


def get_choice_label(label, data_dictionary, language=None):
    """
    Return the label matching selected language or simply just the label.
    """
    if isinstance(label, dict):
        languages = list(label.keys())
        _language = (
            language
            if language in languages
            else data_dictionary.get_language(languages)
        )

        return label[_language]

    return label


def get_choice_label_value(key, value, data_dictionary, language=None):
    """
    Return the label of a choice matching the value if the key xpath is a
    SELECT_ONE otherwise it returns the value unchanged.
    """

    def _get_choice_label_value(lookup):
        _label = None
        element = data_dictionary.get_survey_element(key)
        if element and element.choices is not None:
            for choice in element.choices.options:
                if choice.name == lookup:
                    _label = get_choice_label(choice.label, data_dictionary, language)
                    break

        return _label

    label = None
    if key in data_dictionary.get_select_one_xpaths():
        label = _get_choice_label_value(value)

    if key in data_dictionary.get_select_multiple_xpaths():
        answers = []
        for item in value.split(" "):
            answer = _get_choice_label_value(item)
            answers.append(answer or item)
        if [_i for _i in answers if _i is not None]:
            label = " ".join(answers)

    return label or value


# pylint: disable=too-many-arguments, too-many-positional-arguments
def get_value_or_attachment_uri(
    key,
    value,
    row,
    data_dictionary,
    media_xpaths,
    attachment_list=None,
    show_choice_labels=False,
    language=None,
    host=None,
):
    """
    Gets either the attachment value or the attachment url
    :param key: used to retrieve survey element
    :param value: filename
    :param row: current records row
    :param data_dictionary: form structure
    :param include_images: boolean value to either inlcude images or not
    :param attachment_list: to be used incase row doesn't have ATTACHMENTS key
    :return: value
    """
    if show_choice_labels:
        value = get_choice_label_value(key, value, data_dictionary, language)

    if not media_xpaths:
        return value

    if key in media_xpaths:
        attachments = [
            a
            for a in row.get(ATTACHMENTS, attachment_list or [])
            if a.get("name") == value
        ]
        if attachments:
            value = current_site_url(attachments[0].get("download_url", ""), host)

    return value


def track_task_progress(additions, total=None):
    """
    Updates the current export task with number of submission processed.
    Updates in batches of settings EXPORT_TASK_PROGRESS_UPDATE_BATCH defaults
    to 100.
    :param additions:
    :param total:
    :return:
    """
    batch_size = getattr(
        settings, "EXPORT_TASK_PROGRESS_UPDATE_BATCH", DEFAULT_UPDATE_BATCH
    )
    if additions % batch_size == 0:
        meta = {"progress": additions}
        if total:
            meta.update({"total": total})
        try:
            current_task.update_state(state="PROGRESS", meta=meta)
        except AttributeError:
            pass


def get_abbreviated_xpath(xpath):
    """Returns the abbreviated xpath without the root node

    For example "/data/image1" results in "image1".
    """
    return "/".join(xpath.split("/")[2:])
