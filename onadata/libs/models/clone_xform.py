from django.contrib.auth.models import User
from onadata.apps.viewer.models.data_dictionary import \
    DataDictionary, upload_to
from django.core.files.storage import default_storage
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from onadata.libs.utils.user_auth import get_user_default_project


class CloneXForm(object):
    def __init__(self, xform, username, project_id=-1):
        self.xform = xform
        self.username = username
        self.project_id = project_id

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        user = User.objects.get(username=self.username)
        if self.project_id == -1:
            project = get_user_default_project(user)
        else:
            project = Project.objects.get(pk=self.project_id)
        xls_file_path = upload_to(None, '%s%s.xls' % (
                                  self.xform.id_string,
                                  XForm.CLONED_SUFFIX),
                                  self.username)
        xls_data = default_storage.open(self.xform.xls.name)
        xls_file = default_storage.save(xls_file_path, xls_data)
        self.cloned_form = DataDictionary.objects.create(
            user=user,
            xls=xls_file,
            project=project
        )
