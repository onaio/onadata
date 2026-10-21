# -*- coding: utf-8 -*-
"""
Tests Messaging app implementation.
"""

from __future__ import unicode_literals

from django.contrib.auth import get_user_model

from actstream.models import Action
from rest_framework import exceptions, permissions
from rest_framework.generics import get_object_or_404

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.logger.models import KMSKey
from onadata.apps.messaging.utils import TargetDoesNotExist, get_target
from onadata.libs.permissions import is_organization_admin

User = get_user_model()


def _get_readable_targets(model):
    """Exclude deleted resources and inactive accounts from public reads."""
    filters = {
        "xform": {
            "deleted_at__isnull": True,
            "project__deleted_at__isnull": True,
            "project__organization__is_active": True,
        },
        "project": {"deleted_at__isnull": True, "organization__is_active": True},
        "entitylist": {
            "deleted_at__isnull": True,
            "project__deleted_at__isnull": True,
            "project__organization__is_active": True,
        },
        "user": {"is_active": True},
    }
    return model.objects.filter(**filters.get(model._meta.model_name, {}))


class TargetObjectPermissions(permissions.BasePermission):
    """
    Check target object permissions
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.change_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def get_required_object_permissions(self, method, model_cls):
        """
        Return required object permissions for given request method.
        """

        kwargs = {
            "app_label": model_cls._meta.app_label,
            "model_name": model_cls._meta.model_name,
        }

        if method not in self.perms_map:
            raise exceptions.MethodNotAllowed(method)

        return [perm % kwargs for perm in self.perms_map[method]]

    def has_permission(self, request, view):
        """Authorize list targets before reading activity or aggregate counts."""
        if view.action == "list":
            target_type = request.query_params.get("target_type")
            target_id = request.query_params.get("target_id")
            if not target_type:
                raise exceptions.ParseError("Parameter 'target_type' is missing.")
            if not target_id:
                raise exceptions.ParseError("Parameter 'target_id' is missing.")
            try:
                content_type = get_target(target_type)
            except TargetDoesNotExist as exc:
                raise exceptions.ParseError(
                    f"Unknown target_type {target_type}"
                ) from exc
            target = get_object_or_404(
                _get_readable_targets(content_type.model_class()), pk=target_id
            )
            view.check_object_permissions(request, target)
        return True

    # pylint: disable=unused-variable
    def has_object_permission(self, request, view, obj):
        """
        Check the target object's permissions
        """

        target = obj.target if isinstance(obj, Action) else obj
        if target is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            if isinstance(obj, Action):
                target = get_object_or_404(
                    _get_readable_targets(type(target)), pk=target.pk
                )
            if isinstance(target, KMSKey):
                owner = target.content_object
                if isinstance(owner, OrganizationProfile):
                    owner = owner.user
                if isinstance(owner, User) and not owner.is_active:
                    raise exceptions.NotFound()
        if isinstance(target, User):
            if request.user == target:
                return True
            if request.method in permissions.SAFE_METHODS:
                organization = OrganizationProfile.objects.filter(
                    user=target, user__is_active=True
                ).first()
                return organization is not None and is_organization_admin(
                    request.user, organization
                )
            return False

        perms = self.get_required_object_permissions(request.method, target)

        return request.user.has_perms(perms, target)
