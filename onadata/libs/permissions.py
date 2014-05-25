from guardian.shortcuts import assign_perm
from onadata.apps.main.models.user_profile import UserProfile

CAN_ADD_XFORM = 'can_add_xform'


class ManagerRole(object):
    permissions = ((CAN_ADD_XFORM, UserProfile), )

    @classmethod
    def add(cls, user, obj):
        for permission, klass in cls.permissions:
            if isinstance(obj, klass):
                assign_perm(permission, user, obj)
