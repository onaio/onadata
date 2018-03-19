# -*- coding: utf-8 -*-
"""
Messaging util functions.
"""

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType

from onadata.apps.messaging.constants import APP_LABEL_MAPPING, UNKNOWN_TARGET


class TargetDoesNotExist(Exception):
    """
    Target does not Exist exception class.
    """
    message = UNKNOWN_TARGET


def get_target(target_type):
    """
    Returns a ContentType object if it exists, raises TargetDoesNotExist
    exception if target_type is not known.
    """
    try:
        app_label = APP_LABEL_MAPPING[target_type]

        return ContentType.objects.get(app_label=app_label, model=target_type)
    except (KeyError, ContentType.DoesNotExist):
        raise TargetDoesNotExist()
