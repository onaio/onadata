# -*- coding: utf-8 -*-
"""
Messaging viewset filters module.
"""
from __future__ import unicode_literals
from actstream.models import Action

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import exceptions, filters
from django_filters import rest_framework as rest_filters

from onadata.apps.messaging.utils import TargetDoesNotExist, get_target


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
            target_type = request.query_params.get("target_type")

            if target_type:
                try:
                    target = get_target(target_type)
                except TargetDoesNotExist as exc:
                    raise exceptions.ParseError(
                        f"Unknown target_type {target_type}"
                    ) from exc

                return queryset.filter(target_content_type=target)

            raise exceptions.ParseError(_("Parameter 'target_type' is missing."))

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
            target_id = request.query_params.get("target_id")

            if target_id:
                return queryset.filter(target_object_id=target_id)

            raise exceptions.ParseError(_("Parameter 'target_id' is missing."))

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
