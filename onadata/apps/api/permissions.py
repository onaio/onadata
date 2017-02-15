from django.http import Http404
from rest_framework.permissions import DjangoObjectPermissions
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework import exceptions

from onadata.libs.permissions import (
    CAN_ADD_XFORM_TO_PROFILE,
    CAN_CHANGE_XFORM,
    CAN_DELETE_SUBMISSION)
from onadata.libs.permissions import ReadOnlyRoleNoDownload

from onadata.apps.api.tools import get_user_profile_or_none, \
    check_inherit_permission_from_project

from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import DataView

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class AlternateHasObjectPermissionMixin(object):

    def _has_object_permission(self, request, model_cls, user, obj):
        perms = self.get_required_object_permissions(request.method, model_cls)

        if not user.has_perms(perms, obj):
            # If the user does not have permissions we need to determine if
            # they have read permissions to see 403, or not, and simply see
            # a 404 response.

            if request.method in SAFE_METHODS:
                # Read permissions already checked and failed, no need
                # to make another lookup.
                raise Http404

            read_perms = self.get_required_object_permissions('GET', model_cls)
            if not user.has_perms(read_perms, obj):
                raise Http404

            # Has read permissions.
            return False

        return True


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
        if hasattr(obj, 'shared') and obj.shared and view.action == 'clone':
            return obj

        if request.method == 'DELETE' and view.action == 'labels':
            user = request.user

            return user.has_perm(CAN_CHANGE_XFORM, obj)

        if request.method == 'DELETE' and view.action == 'destroy':
            return request.user.has_perm(CAN_DELETE_SUBMISSION, obj)

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
        # allow anonymous users to view public projects
        if request.user.is_anonymous() and view.action == 'list':
            return True

        if not request.user.is_anonymous() and view.action == 'star':
            return True

        return \
            super(ProjectPermissions, self).has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if view.action == 'share' and request.method == 'PUT':
            remove = request.data.get('remove')
            username = request.data.get('username', '')
            if remove and request.user.username.lower() == username.lower():
                return True

        return super(ProjectPermissions, self).has_object_permission(
            request, view, obj)


class AbstractHasPermissionMixin(object):
    """
    Checks that the requesting user has permissions to access each of the
    models in the `model_classes` instance variable.
    """

    def has_permission(self, request, view):
        # Workaround to ensure DjangoModelPermissions are not applied
        # to the root view when using DefaultRouter.

        if getattr(view, '_ignore_model_permissions', False):
            return True

        perms = []
        for model_class in self.model_classes:
            perms.extend(self.get_required_permissions(
                request.method, model_class))

        if (request.user and
                (request.user.is_authenticated() or
                 not self.authenticated_users_only) and
                request.user.has_perms(perms)):

            return True

        return False


class HasMetadataPermissionMixin(AbstractHasPermissionMixin):
    """
    Use the Project, XForm, or both model classes to check permissions based
    on the request data keys.
    """

    def has_permission(self, request, view):
        if request.data.get("xform") or request.data.get("instance"):
            self.model_classes = [XForm]
        elif request.data.get("project"):
            self.model_classes = [Project]
        else:
            self.model_classes = [Project, XForm]

        return super(HasMetadataPermissionMixin, self).has_permission(
            request, view)


class MetaDataObjectPermissions(AlternateHasObjectPermissionMixin,
                                HasMetadataPermissionMixin,
                                DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        model_cls = obj.content_object.__class__
        user = request.user

        return self._has_object_permission(request, model_cls, user,
                                           obj.content_object)


class AttachmentObjectPermissions(AlternateHasObjectPermissionMixin,
                                  DjangoObjectPermissions):
    authenticated_users_only = False

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user

        return self._has_object_permission(request, model_cls, user,
                                           obj.instance.xform)


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


class DataViewViewsetPermissions(AlternateHasObjectPermissionMixin,
                                 ViewDjangoObjectPermissions,
                                 AbstractHasPermissionMixin,
                                 DjangoObjectPermissions):

    model_classes = [Project]

    def has_permission(self, request, view):
        # To allow individual public dataviews to be visible on
        # `api/v1/dataviews/<pk>` but stop retreival of all dataviews when
        # the dataviews endpoint is queried `api/v1/dataviews`
        return not (request.user.is_anonymous() and view.action == 'list')

    def has_object_permission(self, request, view, obj):
        model_cls = Project
        user = request.user

        if obj.project.shared:
            return True
        return self._has_object_permission(request, model_cls, user,
                                           obj.project)


class RestServiceObjectPermissions(AlternateHasObjectPermissionMixin,
                                   HasMetadataPermissionMixin,
                                   DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user

        return self._has_object_permission(request, model_cls, user, obj.xform)


class WidgetViewSetPermissions(AlternateHasObjectPermissionMixin,
                               ViewDjangoObjectPermissions,
                               AbstractHasPermissionMixin,
                               DjangoObjectPermissions):

    authenticated_users_only = False
    model_classes = [Project]

    def has_permission(self, request, view):
        # User can access the widget with key
        if 'key' in request.query_params or view.action == 'list':
            return True

        return super(WidgetViewSetPermissions, self).has_permission(request,
                                                                    view)

    def has_object_permission(self, request, view, obj):
        model_cls = Project
        user = request.user

        if not (isinstance(obj.content_object, XForm) or
                isinstance(obj.content_object, DataView)):
            return False

        xform = obj.content_object if isinstance(obj.content_object, XForm) \
            else obj.content_object.xform

        if view.action == 'partial_update' and \
                ReadOnlyRoleNoDownload.user_has_role(user, xform):
            # allow readonlynodownload and above roles to edit widget
            return True

        return self._has_object_permission(request, model_cls, user,
                                           obj.content_object.project)


__permissions__ = [DjangoObjectPermissions, IsAuthenticated]


class OrganizationProfilePermissions(DjangoObjectPermissionsAllowAnon):

    def has_object_permission(self, request, view, obj):
        is_authenticated = request and request.user.is_authenticated() and \
                           request.user.username == request.data.get(
                               'username')
        if is_authenticated and request.method == 'DELETE':
            return True
        else:
            return super(OrganizationProfilePermissions,
                         self).has_object_permission(
                request=request, view=view, obj=obj)
