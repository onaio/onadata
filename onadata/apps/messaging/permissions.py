# -*- coding: utf-8 -*-
"""
Tests Messaging app implementation.
"""
from __future__ import unicode_literals

from django.contrib.auth.models import User
from rest_framework import exceptions, permissions


class TargetObjectPermissions(permissions.BasePermission):
    """
    Check target object permissions
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.change_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

    def get_required_object_permissions(self, method, model_cls):
        """
        Return required object permissions for given request method.
        """

        kwargs = {
            'app_label': model_cls._meta.app_label,
            'model_name': model_cls._meta.model_name
        }

        if method not in self.perms_map:
            raise exceptions.MethodNotAllowed(method)

        return [perm % kwargs for perm in self.perms_map[method]]

    # pylint: disable=unused-variable
    def has_object_permission(self, request, view, obj):
        """
        Check the target object's permissions
        """

        # the `can_view`` permission is needed for the target object
        target = obj.target
        if isinstance(target, User):
            return request.user == target

        perms = self.get_required_object_permissions(request.method, target)

        return request.user.has_perms(perms, target)
