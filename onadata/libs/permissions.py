from guardian.shortcuts import assign_perm
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models import XForm

CAN_ADD_XFORM = 'can_add_xform'
CAN_CHANGE_XFORM = 'change_xform'


class ManagerRole(object):
    permissions = (
        (CAN_ADD_XFORM, (UserProfile, OrganizationProfile)),
        (CAN_CHANGE_XFORM, XForm)
    )

    @classmethod
    def add(cls, user, obj):
        for permission, klass in cls.permissions:
            if isinstance(obj, klass):
                assign_perm(permission, user, obj)
