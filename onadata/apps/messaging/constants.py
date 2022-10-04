# -*- coding: utf-8 -*-
"""
Messaging constant variables.
"""

from __future__ import unicode_literals

from builtins import str as text

from django.utils.translation import gettext as _

XFORM = text('xform')
PROJECT = text('project')
USER = text('user')
EXPORT = text('export')

APP_LABEL_MAPPING = {
    XFORM: 'logger',
    PROJECT: 'logger',
    USER: 'auth',
}

MESSAGE = 'message'
UNKNOWN_TARGET = _("Unknown target.")
USER_ADDED_TO_PROJECT = "user_added_to_project"
USER_REMOVED_FROM_PROJECT = "user_removed_from_project"
PROJECT_CREATED = "project_created"
PROJECT_EDITED = "project_edited"
PROJECT_SHARED = "project_shared"
PROJECT_DELETED = "project_deleted"
SUBMISSION_CREATED = "submission_created"
SUBMISSION_EDITED = "submission_edited"
SUBMISSION_DELETED = "submission_deleted"
SUBMISSION_REVIEWED = "submission_reviewed"
FORM_UPDATED = "form_updated"
FORM_CREATED = "form_created"
FORM_DELETED = "form_deleted"
EXPORT_CREATED = "export_created"
EXPORT_DELETED = "export_deleted"
PERMISSION_GRANTED = "permission_granted"
PERMISSION_REVOKED = "permission_revoked"
MESSAGE_VERBS = [
    MESSAGE, SUBMISSION_REVIEWED, SUBMISSION_CREATED, SUBMISSION_EDITED,
    SUBMISSION_DELETED, FORM_UPDATED, FORM_CREATED, FORM_DELETED,
    EXPORT_CREATED, EXPORT_DELETED, PROJECT_EDITED, PROJECT_SHARED,
    PROJECT_CREATED, USER_ADDED_TO_PROJECT, USER_REMOVED_FROM_PROJECT,
    PROJECT_DELETED
]
VERB_TOPIC_DICT = {
    SUBMISSION_CREATED: "submission/created",
    SUBMISSION_EDITED: "submission/edited",
    SUBMISSION_DELETED: "submission/deleted",
    SUBMISSION_REVIEWED: "submission/reviewed",
    FORM_UPDATED: "form/updated"
}
