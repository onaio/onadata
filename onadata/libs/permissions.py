from guardian.shortcuts import assign_perm
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models import XForm

CAN_ADD_XFORM_TO_PROFILE = 'can_add_xform'
CAN_CHANGE_XFORM = 'change_xform'
CAN_ADD_XFORM = 'logger.add_xform'
CAN_DELETE_XFORM = 'logger.delete_xform'


class ManagerRole(object):
    permissions = (
        (CAN_ADD_XFORM_TO_PROFILE, (UserProfile, OrganizationProfile)),
        (CAN_ADD_XFORM, XForm),
        (CAN_DELETE_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm)
    )

    @classmethod
    def add(cls, user, obj):
        for permission, klass in cls.permissions:
            if isinstance(obj, klass):
                assign_perm(permission, user, obj)
