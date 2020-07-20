# -*- coding: utf-8 -*-
"""
Messaging constant variables.
"""

from __future__ import unicode_literals

from builtins import str as text

from django.utils.translation import ugettext as _

XFORM = text('xform')
PROJECT = text('project')
USER = text('user')

APP_LABEL_MAPPING = {
    XFORM: 'logger',
    PROJECT: 'logger',
    USER: 'auth',
}

MESSAGE = 'message'
UNKNOWN_TARGET = _("Unknown target.")
SUBMISSION_CREATED = "submission/created"
SUBMISSION_EDITED = "submission/edited"
SUBMISSION_DELETED = "submission/deleted"
SUBMISSION_REVIEWED = "submission/reviewed"
FORM_UPDATED = "form/updated"
MESSAGE_VERBS = [
    MESSAGE, SUBMISSION_REVIEWED, SUBMISSION_CREATED, SUBMISSION_EDITED,
    SUBMISSION_DELETED, FORM_UPDATED]
