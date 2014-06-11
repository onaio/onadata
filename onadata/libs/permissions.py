from guardian.shortcuts import assign_perm
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models import XForm

CAN_ADD_XFORM_TO_PROFILE = 'can_add_xform'
CAN_CHANGE_XFORM = 'change_xform'
CAN_ADD_XFORM = 'logger.add_xform'
CAN_DELETE_XFORM = 'logger.delete_xform'
CAN_VIEW_XFORM = 'view_xform'
CAN_ADD_SUBMISSIONS = 'report_xform'


class Role(object):
    permissions = None

    @classmethod
    def add(cls, user, obj):
        for permission, klass in cls.permissions:
            if isinstance(obj, klass):
                assign_perm(permission, user, obj)


class ManagerRole(Role):
    permissions = (
        (CAN_ADD_XFORM_TO_PROFILE, (UserProfile, OrganizationProfile)),
        (CAN_ADD_XFORM, XForm),
        (CAN_DELETE_XFORM, XForm),
        (CAN_CHANGE_XFORM, XForm)
    )


class ReadOnlyRole(Role):
    permissions = (
        (CAN_VIEW_XFORM, XForm),
    )


class DataEntryRole(Role):
    permissions = (
        (CAN_VIEW_XFORM, XForm),
        (CAN_ADD_SUBMISSIONS, XForm),
    )
