# -*- coding: utf-8 -*-
"""
Messaging constant variables.
"""

from __future__ import unicode_literals

from builtins import str  # pylint: disable=W0622

from django.utils.translation import ugettext as _

XFORM = str('xform')
PROJECT = str('project')
USER = str('user')

APP_LABEL_MAPPING = {
    XFORM: 'logger',
    PROJECT: 'logger',
    USER: 'auth',
}

MESSAGE = 'message'
UNKNOWN_TARGET = _("Unknown target.")
