# -*- coding: utf-8 -*-
"""
Messaging constant variables.
"""

from __future__ import unicode_literals

from django.utils.translation import ugettext as _


APP_LABEL_MAPPING = {
    'xform': 'logger',
    'projects': 'logger',
    'user': 'auth',
}

MESSAGE = 'message'
UNKNOWN_TARGET = _("Unknown target.")
