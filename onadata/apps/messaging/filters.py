# -*- coding: utf-8 -*-
"""
Messaging viewset filters module.
"""
from __future__ import unicode_literals

from rest_framework import exceptions, filters

from onadata.apps.messaging.utils import TargetDoesNotExist, get_target


class TargetTypeFilterBackend(filters.BaseFilterBackend):
    """
    A filter backend that filters by target type.
    """

    def filter_queryset(self, request, queryset, view):
        if view.action == 'list':
            target_type = request.query_params.get('target_type')

            if target_type:
                try:
                    target = get_target(target_type)
                except TargetDoesNotExist:
                    raise exceptions.ParseError(
                        "Unknown target_type {}".format(target_type))

                return queryset.filter(target_content_type=target)

            raise exceptions.ParseError("Parameter 'target_type' is missing.")

        return queryset


class TargetIDFilterBackend(filters.BaseFilterBackend):
    """
    A filter backend that filters by target id.
    """

    def filter_queryset(self, request, queryset, view):
        if view.action == 'list':
            target_id = request.query_params.get('target_id')

            if target_id:
                return queryset.filter(target_object_id=target_id)

            raise exceptions.ParseError("Parameter 'target_id' is missing.")

        return queryset
