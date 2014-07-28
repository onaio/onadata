from rest_framework.permissions import DjangoObjectPermissions, IsAuthenticated
from onadata.libs.permissions import CAN_ADD_XFORM_TO_PROFILE, CAN_CHANGE_XFORM
from onadata.apps.api.tools import get_user_profile_or_none


class ViewDjangoObjectPermissions(DjangoObjectPermissions):
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


class DjangoObjectPermissionsAllowAnon(DjangoObjectPermissions):
    authenticated_users_only = False


class XFormPermissions(DjangoObjectPermissions):

    authenticated_users_only = False

    def has_permission(self, request, view):
        owner = view.kwargs.get('owner')
        is_authenticated = request and request.user.is_authenticated()

        if is_authenticated and view.action == 'create':
            owner = owner or request.user.username

            return request.user.has_perm(CAN_ADD_XFORM_TO_PROFILE,
                                         get_user_profile_or_none(owner))

        return super(XFormPermissions, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.method == 'DELETE' and view.action == 'labels':
            user = request.user

            return user.has_perms([CAN_CHANGE_XFORM], obj)

        return super(XFormPermissions, self).has_object_permission(
            request, view, obj)


class UserProfilePermissions(DjangoObjectPermissions):

    authenticated_users_only = False

    def has_permission(self, request, view):
        # allow anonymous users to create new profiles
        if request.user.is_anonymous() and view.action == 'create':
            return True

        return \
            super(UserProfilePermissions, self).has_permission(request, view)


class ProjectPermissions(DjangoObjectPermissions):

    authenticated_users_only = False

    def has_permission(self, request, view):
        # allow anonymous to view public projects
        if request.user.is_anonymous() and view.action == 'list':
            return True

        if not request.user.is_anonymous() and view.action == 'star':
            return True

        return \
            super(ProjectPermissions, self).has_permission(request, view)


class MetaDataObjectPermissions(DjangoObjectPermissions):
    """Use xform permissions for MetaData objects"""
    def has_object_permission(self, request, view, obj):
        return super(MetaDataObjectPermissions, self).has_object_permission(
            request, view, obj.xform)

__permissions__ = [DjangoObjectPermissions, IsAuthenticated]
