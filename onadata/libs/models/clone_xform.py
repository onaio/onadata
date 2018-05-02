from django.contrib.auth.models import User
from onadata.apps.viewer.models.data_dictionary import \
    DataDictionary, upload_to
from django.core.files.storage import default_storage
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.user_auth import get_user_default_project


class CloneXForm(object):
    def __init__(self, xform, username, project=None):
        self.xform = xform
        self.username = username
        self.project = project

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        user = User.objects.get(username=self.username)
        project = self.project or get_user_default_project(user)
        xls_file_path = upload_to(None, '%s%s.xls' % (
                                  self.xform.id_string,
                                  XForm.CLONED_SUFFIX),
                                  self.username)
        xls_data = default_storage.open(self.xform.xls.name)
        xls_file = default_storage.save(xls_file_path, xls_data)
        self.cloned_form = DataDictionary.objects.create(
            user=user,
            created_by=user,
            xls=xls_file,
            project=project
        )
