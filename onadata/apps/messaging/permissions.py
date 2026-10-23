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
from onadata.apps.messaging.constants import APP_LABEL_MAPPING
from onadata.apps.messaging.utils import (
    TargetDoesNotExist,
    get_available_targets,
    get_target,
)
from onadata.libs.permissions import is_organization_admin

User = get_user_model()


class TargetObjectPermissions(permissions.BasePermission):
    """
    Check target object permissions
    """

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
                get_available_targets(content_type.model_class()), pk=target_id
            )
            view.check_object_permissions(request, target)
        return True

    # pylint: disable=unused-variable
    def has_object_permission(self, request, view, obj):
        """
        Check the target object's permissions
        """

        if isinstance(obj, Action):
            content_type = obj.target_content_type
            model = content_type.model_class() if content_type else None
            if model is None or APP_LABEL_MAPPING.get(model._meta.model_name) != (
                model._meta.app_label
            ):
                raise exceptions.NotFound()
            target = get_object_or_404(
                get_available_targets(model), pk=obj.target_object_id
            )
        else:
            target = obj
        if isinstance(target, User):
            if request.user == target:
                return True
            organization = OrganizationProfile.objects.filter(
                user=target, user__is_active=True
            ).first()
            return organization is not None and is_organization_admin(
                request.user, organization
            )

        meta = target._meta
        return request.user.has_perm(f"{meta.app_label}.view_{meta.model_name}", target)
