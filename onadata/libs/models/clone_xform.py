# -*- coding: utf-8 -*-
"""
CloneXForm class model.
"""
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage

from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.data_dictionary import DataDictionary, upload_to
from onadata.libs.utils.user_auth import get_user_default_project


class CloneXForm:
    """The class takes an existing form's XLSForm and publishes it as a new form."""

    def __init__(self, xform, username, project=None):
        self.xform = xform
        self.username = username
        self.project = project
        self.cloned_form = None

    @property
    def user(self):
        """Returns a User object for the given ``self.username``."""
        return get_user_model().objects.get(username=self.username)

    def save(self, **kwargs):
        """Publishes an exiting form's XLSForm as a new form."""
        user = self.user
        project = self.project or get_user_default_project(user)
        xls_file_path = upload_to(
            None,
            f"{self.xform.id_string}{XForm.CLONED_SUFFIX}.xlsx",
            self.username,
        )
        xls_data = default_storage.open(self.xform.xls.name)
        xls_file = default_storage.save(xls_file_path, xls_data)
        self.cloned_form = DataDictionary.objects.create(
            user=user, created_by=user, xls=xls_file, project=project
        )
