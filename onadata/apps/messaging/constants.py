# -*- coding: utf-8 -*-
"""
Messaging constant variables.
"""

from __future__ import unicode_literals

from builtins import str as text

from django.utils.translation import gettext as _

XFORM = text("xform")
PROJECT = text("project")
USER = text("user")
KMS_KEY = text("kmskey")

APP_LABEL_MAPPING = {
    XFORM: "logger",
    PROJECT: "logger",
    USER: "auth",
    KMS_KEY: "logger",
}

MESSAGE = "message"
UNKNOWN_TARGET = _("Unknown target.")
SUBMISSION_CREATED = "submission_created"
SUBMISSION_EDITED = "submission_edited"
SUBMISSION_DELETED = "submission_deleted"
SUBMISSION_REVIEWED = "submission_reviewed"
FORM_UPDATED = "form_updated"
KMS_KEY_ROTATED = "kmskey_rotated"
MESSAGE_VERBS = [
    MESSAGE,
    SUBMISSION_REVIEWED,
    SUBMISSION_CREATED,
    SUBMISSION_EDITED,
    SUBMISSION_DELETED,
    FORM_UPDATED,
    KMS_KEY_ROTATED,
]
VERB_TOPIC_DICT = {
    SUBMISSION_CREATED: "submission/created",
    SUBMISSION_EDITED: "submission/edited",
    SUBMISSION_DELETED: "submission/deleted",
    SUBMISSION_REVIEWED: "submission/reviewed",
    FORM_UPDATED: "form/updated",
    KMS_KEY_ROTATED: "kmskey/rotated",
}
