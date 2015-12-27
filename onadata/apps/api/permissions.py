from rest_framework.permissions import DjangoObjectPermissions,\
    DjangoModelPermissionsOrAnonReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework import exceptions

from onadata.libs.permissions import (
    CAN_ADD_XFORM_TO_PROFILE,
    CAN_CHANGE_XFORM,
    CAN_DELETE_SUBMISSION)

from onadata.apps.api.tools import get_user_profile_or_none, \
    check_inherit_permission_from_project
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models import DataView


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


class AbstractHasObjectPermissionMixin(object):
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


class HasObjectPermissionMixin(AbstractHasObjectPermissionMixin):
    """
    Use the Project, XForm, or both model classes to check permissions based
    on the request data keys.
    """

    def has_permission(self, request, view):
        if request.data.get("xform"):
            self.model_classes = [XForm]
        elif request.data.get("project"):
            self.model_classes = [Project]
        else:
            self.model_classes = [Project, XForm]

        return super(HasObjectPermissionMixin, self).has_permission(
            request, view)


class MetaDataObjectPermissions(HasObjectPermissionMixin,
                                DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        view.model = obj.content_object.__class__

        return super(MetaDataObjectPermissions, self)\
            .has_object_permission(request, view, obj.content_object)


class RestServiceObjectPermissions(HasObjectPermissionMixin,
                                   DjangoObjectPermissions):

    def has_object_permission(self, request, view, obj):
        view.model = XForm

        return super(RestServiceObjectPermissions, self)\
            .has_object_permission(request, view, obj.xform)


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
                                 AbstractHasObjectPermissionMixin,
                                 DjangoObjectPermissions):

    model_classes = [Project]

    def has_object_permission(self, request, view, obj):
        # Override the default Rest Framework model_cls
        view.model = Project

        return super(DataViewViewsetPermissions, self).has_object_permission(
            request, view, obj.project)


class WidgetViewSetPermissions(ViewDjangoObjectPermissions,
                               AbstractHasObjectPermissionMixin,
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
        # Override the default Rest Framework model_cls
        view.model = Project

        if not (isinstance(obj.content_object, XForm) or
                isinstance(obj.content_object, DataView)):
            return False

        return super(WidgetViewSetPermissions, self).has_object_permission(
            request, view, obj.content_object.project)


__permissions__ = [DjangoObjectPermissions, IsAuthenticated]
