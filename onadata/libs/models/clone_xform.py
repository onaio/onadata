from django.contrib.auth.models import User
from onadata.apps.viewer.models.data_dictionary import DataDictionary, upload_to
from django.core.files.storage import default_storage
from onadata.apps.logger.models.xform import XForm

class CloneXForm(object):
    def __init__(self, xform, username):
        self.xform = xform
        self.username = username

    @property
    def user(self):
        return User.objects.get(username=self.username)
