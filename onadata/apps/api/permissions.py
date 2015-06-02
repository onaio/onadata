from rest_framework.permissions import DjangoObjectPermissions,\
    DjangoModelPermissionsOrAnonReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework import exceptions

from onadata.libs.permissions import CAN_ADD_XFORM_TO_PROFILE
from onadata.libs.permissions import CAN_CHANGE_XFORM
from onadata.apps.api.tools import get_user_profile_or_none, \
    check_inherit_permission_from_project
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project


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

        if 'pk' in view.kwargs:
            check_inherit_permission_from_project(view.kwargs['pk'],
                                                  request.user)

        if is_authenticated and view.action == 'create':
            owner = owner or request.user.username

            return request.user.has_perm(CAN_ADD_XFORM_TO_PROFILE,
                                         get_user_profile_or_none(owner))

        return super(XFormPermissions, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if obj.shared and view.action == 'clone':
            return obj

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

    def has_object_permission(self, request, view, obj):
        if view.action == 'share' and request.method == 'PUT':
            if request.DATA.get('remove'):
                if request.user.username == request.DATA.get('username'):
                    return True

        return super(ProjectPermissions, self).has_object_permission(
            request, view, obj)


class HasXFormObjectPermissionMixin(object):

    """Use XForm permissions for Attachment objects"""

    def has_permission(self, request, view):
        model_cls = None

        # Workaround to ensure DjangoModelPermissions are not applied
        # to the root view when using DefaultRouter.
        if (model_cls is None and
                getattr(view, '_ignore_model_permissions', False)):
            return True

        model_cls = XForm
        perms = self.get_required_permissions(request.method, model_cls)

        if (request.user and
                (request.user.is_authenticated() or
                 not self.authenticated_users_only) and
                request.user.has_perms(perms)):

            return True

        return False


class HasProjectObjectPermissionMixin(object):
    """Use Project permissions for DataView objects"""

    def has_permission(self, request, view):
        model_cls = None

        # Workaround to ensure DjangoModelPermissions are not applied
        # to the root view when using DefaultRouter.
        if (model_cls is None and
                getattr(view, '_ignore_model_permissions', False)):
            return True

        model_cls = Project
        perms = self.get_required_permissions(request.method, model_cls)

        if (request.user and
                (request.user.is_authenticated() or
                 not self.authenticated_users_only) and
                request.user.has_perms(perms)):

            return True

        return False


class MetaDataObjectPermissions(HasXFormObjectPermissionMixin,
                                DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        view.model = XForm

        return super(MetaDataObjectPermissions, self).has_object_permission(
            request, view, obj.xform)


class AttachmentObjectPermissions(DjangoObjectPermissions):
    authenticated_users_only = False

    def has_object_permission(self, request, view, obj):
        view.model = XForm

        return super(AttachmentObjectPermissions, self).has_object_permission(
            request, view, obj.instance.xform)


class ConnectViewsetPermissions(IsAuthenticated):

    def has_permission(self, request, view):
        if view.action == 'reset':
            return True

        return super(ConnectViewsetPermissions, self)\
            .has_permission(request, view)


class UserViewSetPermissions(DjangoModelPermissionsOrAnonReadOnly):

    def has_permission(self, request, view):

        if request.user.is_anonymous() and view.action == 'list':
            if request.GET.get('search'):
                raise exceptions.NotAuthenticated()

        return \
            super(UserViewSetPermissions, self).has_permission(request, view)


class DataViewViewsetPermissions(ViewDjangoObjectPermissions,
                                 HasProjectObjectPermissionMixin,
                                 DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        view.model = Project

        return super(DataViewViewsetPermissions, self).has_object_permission(
            request, view, obj.project)


class WidgetViewSetPermissions(ViewDjangoObjectPermissions,
                               HasProjectObjectPermissionMixin,
                               DjangoObjectPermissions):

    authenticated_users_only = False

    def has_permission(self, request, view):
        view.model = Project

        return super(WidgetViewSetPermissions, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):

        return super(WidgetViewSetPermissions, self).has_object_permission(
            request, view, obj.project)


__permissions__ = [DjangoObjectPermissions, IsAuthenticated]
