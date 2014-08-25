from django.contrib.auth.models import User
from onadata.apps.viewer.models.data_dictionary import \
    DataDictionary, upload_to
from django.core.files.storage import default_storage
from onadata.apps.logger.models.xform import XForm


class CloneXForm(object):
    def __init__(self, xform, username):
        self.xform = xform
        self.username = username

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        user = User.objects.get(username=self.username)
        xls_file_path = upload_to(None, '%s%s.xls' % (
                                  self.xform.id_string,
                                  XForm.CLONED_SUFFIX),
                                  self.username)
        xls_data = default_storage.open(self.xform.xls.name)
        xls_file = default_storage.save(xls_file_path, xls_data)
        self.cloned_form = DataDictionary.objects.create(
            user=user,
            xls=xls_file
        )
