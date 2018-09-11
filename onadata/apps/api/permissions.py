# -*- coding=utf-8 -*-
"""
API permissions module.
"""
from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.conf import settings

from rest_framework import exceptions
from rest_framework.permissions import (
    BasePermission, DjangoModelPermissionsOrAnonReadOnly,
    DjangoObjectPermissions, IsAuthenticated)

from onadata.apps.api.tools import (check_inherit_permission_from_project,
                                    get_instance_xform_or_none,
                                    get_user_profile_or_none)
from onadata.apps.logger.models import DataView, Instance, Project, XForm
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.permissions import (CAN_ADD_XFORM_TO_PROFILE,
                                      CAN_CHANGE_XFORM, CAN_DELETE_SUBMISSION,
                                      ManagerRole, ReadOnlyRoleNoDownload)

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class AlternateHasObjectPermissionMixin(object):  # pylint: disable=R0903
    """
    AlternateHasObjectPermissionMixin - checks if user has read permissions.
    """

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
    """
    View DjangoObjectPermissions - applies view_<model_name> permissions for
    GET requests.
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


class ExportDjangoObjectPermission(AlternateHasObjectPermissionMixin,
                                   ViewDjangoObjectPermissions):
    """
    Export DjangoObjectPermission - checks XForm permissions for export
    permissions.
    """
    authenticated_users_only = False
    perms_map = {
        'GET': ['logger.view_xform'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['logger.add_xform'],
        'PUT': ['logger.change_xform'],
        'PATCH': ['logger.change_xform'],
        'DELETE': ['logger.delete_xform'],
    }

    def has_permission(self, request, view):
        is_authenticated = (request and request.user and
                            request.user.is_authenticated())

        if not is_authenticated:
            view._ignore_model_permissions = True  # pylint: disable=W0212

        if view.action == 'destroy' and is_authenticated:
            return request.user.has_perms(['logger.delete_xform'])

        return super(ExportDjangoObjectPermission, self).has_permission(
            request, view)

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user
        return (obj.xform.shared_data or obj.xform.project.shared) or\
            self._has_object_permission(request, model_cls, user, obj.xform)


class DjangoObjectPermissionsAllowAnon(DjangoObjectPermissions):
    """
    DjangoObjectPermissionsAllowAnon - allow anonymous access permission.
    """
    authenticated_users_only = False


class XFormPermissions(DjangoObjectPermissions):
    """
    XFormPermissions - custom permissions check on XForm viewset.
    """
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


class SubmissionReviewPermissions(XFormPermissions):
    """
    Custom Permission Checks for SubmissionReviews
    """
    perms_map = {
        'GET': [],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['logger.add_xform'],
        'PUT': ['logger.change_xform'],
        'PATCH': ['logger.change_xform'],
        'DELETE': ['logger.delete_xform'],
    }

    def has_permission(self, request, view):
        """
        Custom has_permission method
        """
        is_authenticated = request and request.user.is_authenticated()

        if is_authenticated and view.action == 'create':

            # Handle bulk create
            # if doing a bulk create we will fail the entire process if the
            # user lacks permissions for even one instance
            if isinstance(request.data, list):
                instance_ids = list(set([_['instance'] for _ in request.data]))
                instances = Instance.objects.filter(
                    id__in=instance_ids).only('xform').order_by().distinct()
                for instance in instances:
                    if not request.user.has_perm(
                            CAN_CHANGE_XFORM, instance.xform):
                        return False
                return True  # everything is okay

            # Handle single create like normal
            instance_id = request.data.get('instance')
            xform = get_instance_xform_or_none(instance_id)
            return request.user.has_perm(CAN_CHANGE_XFORM, xform)

        return super(SubmissionReviewPermissions, self).has_permission(
            request, view)

    def has_object_permission(self, request, view, obj):
        """
        Custom has_object_permission method
        """
        if (request.method == 'DELETE' and view.action == 'destroy') or (
                request.method == 'PATCH' and view.action == 'partial_update'):
            return ManagerRole.user_has_role(request.user, obj.instance.xform)

        return super(SubmissionReviewPermissions, self).has_object_permission(
            request, view, obj)


class UserProfilePermissions(DjangoObjectPermissions):
    """
    UserProfilePermissions - allows anonymous users to create a profile.
    """

    authenticated_users_only = False

    def has_permission(self, request, view):
        # allow anonymous users to create new profiles
        if request.user.is_anonymous() and view.action == 'create':
            return True

        if view.action in ['send_verification_email', 'verify_email']:
            enable_email_verification = getattr(
                settings, 'ENABLE_EMAIL_VERIFICATION', False
            )
            if enable_email_verification is None or\
                    not enable_email_verification:
                return False

            if view.action == 'send_verification_email':
                return request.user.username == request.data.get('username')

        return \
            super(UserProfilePermissions, self).has_permission(request, view)


class ProjectPermissions(DjangoObjectPermissions):
    """
    ProjectPermissions - allows anonymous to star a project.
    """

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


class AbstractHasPermissionMixin(object):  # pylint: disable=R0903
    """
    Checks that the requesting user has permissions to access each of the
    models in the `model_classes` instance variable.
    """

    def has_permission(self, request, view):
        """
        Check request.user is authenticated and the user has permissions.
        """
        # Workaround to ensure DjangoModelPermissions are not applied
        # to the root view when using DefaultRouter.

        if getattr(view, '_ignore_model_permissions', False):
            return True

        perms = []
        for model_class in self.model_classes:
            perms.extend(
                self.get_required_permissions(request.method, model_class))

        if (request.user and (request.user.is_authenticated()
                              or not self.authenticated_users_only)
                and request.user.has_perms(perms)):

            return True

        return False


# pylint: disable=R0903
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
    """
    MetaData ObjectPermissions - apply Xform permision for given response.
    """

    def has_object_permission(self, request, view, obj):
        model_cls = obj.content_object.__class__
        user = request.user

        # xform instance object perms are not added explicitly to user perms
        if model_cls == Instance:
            model_cls = XForm
            xform_obj = obj.content_object.xform

            return self._has_object_permission(request, model_cls, user,
                                               xform_obj)

        return self._has_object_permission(request, model_cls, user,
                                           obj.content_object)


class AttachmentObjectPermissions(AlternateHasObjectPermissionMixin,
                                  DjangoObjectPermissions):
    """
    Attachment ObjectPermissions - apply XForm model options.
    """
    authenticated_users_only = False

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user

        return self._has_object_permission(request, model_cls, user,
                                           obj.instance.xform)


class ConnectViewsetPermissions(IsAuthenticated):
    """
    ConnectViewsetPermissions - allows reset passwords to all users.
    """

    def has_permission(self, request, view):
        if view.action == 'reset':
            return True

        return super(ConnectViewsetPermissions, self)\
            .has_permission(request, view)


class UserViewSetPermissions(DjangoModelPermissionsOrAnonReadOnly):
    """
    User ViewSetPermissions - do not allow user search for anonymous users.
    """

    def has_permission(self, request, view):

        if request.user.is_anonymous() and view.action == 'list':
            if request.GET.get('search'):
                raise exceptions.NotAuthenticated()

        return \
            super(UserViewSetPermissions, self).has_permission(request, view)


class DataViewViewsetPermissions(
        AlternateHasObjectPermissionMixin, ViewDjangoObjectPermissions,
        AbstractHasPermissionMixin, DjangoObjectPermissions):
    """
    DataView ViewSetPermissions - applies projet permissions to a filtered
    dataset.
    """

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
    """
    RestService ObjectPermissions - apply XForm permisions for a RestService
    model.
    """

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user

        return self._has_object_permission(request, model_cls, user, obj.xform)


class WidgetViewSetPermissions(
        AlternateHasObjectPermissionMixin, ViewDjangoObjectPermissions,
        AbstractHasPermissionMixin, DjangoObjectPermissions):
    """
    Widget ViewSetPermissions - apply project permissions check.
    """

    authenticated_users_only = False
    model_classes = [Project]

    def has_permission(self, request, view):
        # User can access the widget with key
        if 'key' in request.query_params or view.action == 'list':
            return True

        return super(WidgetViewSetPermissions, self).has_permission(
            request, view)

    def has_object_permission(self, request, view, obj):
        model_cls = Project
        user = request.user

        if not isinstance(obj.content_object, (XForm, DataView)):
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
    """
    OrganizationProfilePermissions - allow authenticated users to delete an org
    """

    def has_object_permission(self, request, view, obj):
        is_authenticated = request and request.user.is_authenticated() and \
                           request.user.username == request.data.get(
                               'username')
        if is_authenticated and request.method == 'DELETE':
            return True

        return super(OrganizationProfilePermissions, self)\
            .has_object_permission(request=request, view=view, obj=obj)


class OpenDataViewSetPermissions(IsAuthenticated,
                                 AlternateHasObjectPermissionMixin,
                                 DjangoObjectPermissionsAllowAnon):
    """
    OpenDataViewSetPermissions - allow anonymous access to schema and data
    end-points of an open dataset.
    """

    def has_permission(self, request, view):
        if request.user.is_anonymous() and view.action in ['schema', 'data']:
            return True

        return super(OpenDataViewSetPermissions, self).has_permission(
            request, view)

    def has_object_permission(self, request, view, obj):
        model_cls = XForm
        user = request.user

        return self._has_object_permission(request, model_cls, user,
                                           obj.content_object)


class IsAuthenticatedSubmission(BasePermission):
    """
    IsAuthenticatedSubmission - checks if profile requires authentication
    during a submission request.
    """

    def has_permission(self, request, view):
        username = view.kwargs.get('username')
        if request.method in ['HEAD', 'POST'] and request.user.is_anonymous():
            if username is None:
                # raises a permission denied exception, forces authentication
                return False
            else:
                user = get_object_or_404(User, username=username.lower())

                profile, _ = UserProfile.objects.get_or_create(user=user)

                if profile.require_auth:
                    # raises a permission denied exception,
                    # forces authentication
                    return False

        return True
