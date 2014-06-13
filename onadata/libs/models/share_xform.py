from django.contrib.auth.models import User
from onadata.libs.permissions import ROLES


class ShareXForm(object):
    def __init__(self, xform, username, role):
        self.xform = xform
        self.username = username
        self.role = role

    @property
    def user(self):
        return User.objects.get(username=self.username)

    def save(self, **kwargs):
        role = ROLES.get(self.role)

        if role and self.user and self.xform:
            role.add(self.user, self.xform)
