# -*- coding: utf-8 -*-
"""
Messaging viewset filters module.
"""

from __future__ import unicode_literals

from django.contrib.auth import get_user_model

from actstream.models import Action
from django_filters import rest_framework as rest_filters
from rest_framework import filters

from onadata.apps.messaging.utils import get_target

User = get_user_model()


DATETIME_LOOKUPS = [
    "exact",
    "gt",
    "lt",
    "gte",
    "lte",
    "year",
    "year__gt",
    "year__lt",
    "year__gte",
    "year__lte",
    "month",
    "month__gt",
    "month__lt",
    "month__gte",
    "month__lte",
    "day",
    "day__gt",
    "day__lt",
    "day__gte",
    "day__lte",
    "hour",
    "hour__gt",
    "hour__lt",
    "hour__gte",
    "hour__lte",
    "minute",
    "minute__gt",
    "minute__lt",
    "minute__gte",
    "minute__lte",
]


class ActionFilterSet(rest_filters.FilterSet):
    class Meta:
        model = Action
        fields = {"verb": ["exact"], "timestamp": DATETIME_LOOKUPS}


class TargetTypeFilterBackend(filters.BaseFilterBackend):
    """
    A filter backend that filters by target type.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Return a filtered queryset.
        """

        if view.action == "list":
            # TargetObjectPermissions validates list parameters before filtering.
            target = get_target(request.query_params["target_type"])
            return queryset.filter(target_content_type=target)

        return queryset


class TargetIDFilterBackend(filters.BaseFilterBackend):
    """
    A filter backend that filters by target id.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Return a filtered queryset.
        """

        if view.action == "list":
            return queryset.filter(target_object_id=request.query_params["target_id"])

        return queryset


# pylint: disable=too-few-public-methods
class UserFilterBackend(filters.BaseFilterBackend):
    """
    A filter backend that filters by username.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Return a filtered queryset.
        """

        if view.action == "list":
            username = request.query_params.get("user")
            try:
                user = User.objects.get(username=username)
                return queryset.filter(actor_object_id=user.id)
            except User.DoesNotExist:
                return queryset

        return queryset
