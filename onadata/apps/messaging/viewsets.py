# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""

from __future__ import unicode_literals

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from actstream.models import Action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from onadata.apps.messaging.constants import MESSAGE_VERBS
from onadata.apps.messaging.filters import (
    ActionFilterSet,
    TargetIDFilterBackend,
    TargetTypeFilterBackend,
    UserFilterBackend,
)
from onadata.apps.messaging.permissions import TargetObjectPermissions
from onadata.apps.messaging.serializers import MessageSerializer
from onadata.libs.pagination import CountOverridablePageNumberPagination


# pylint: disable=too-many-ancestors
@method_decorator(cache_page(10 * 60), name="list")
class MessagingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for the Messaging app - implements /messaging API endpoint
    """

    serializer_class = MessageSerializer
    queryset = Action.objects.filter(verb__in=MESSAGE_VERBS)
    permission_classes = [IsAuthenticated, TargetObjectPermissions]
    filter_backends = (
        TargetTypeFilterBackend,
        TargetIDFilterBackend,
        UserFilterBackend,
        DjangoFilterBackend,
    )
    filterset_class = ActionFilterSet
    pagination_class = CountOverridablePageNumberPagination
    # cached count of the filtered queryset for the current request, reused
    # across pagination and Link header generation to avoid repeat COUNT(*)
    record_count = None

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self, count=self.record_count
        )

    def list(self, request, *args, **kwargs):
        headers = None
        queryset = self.filter_queryset(self.get_queryset())
        retrieval_threshold = getattr(settings, "MESSAGE_RETRIEVAL_THRESHOLD", 500)
        pagination_keys = [
            self.paginator.page_query_param,
            self.paginator.page_size_query_param,
        ]
        query_param_keys = self.request.query_params
        has_pagination_params = any(k in query_param_keys for k in pagination_keys)

        # Only count to decide auto-pagination; when pagination is explicitly
        # requested the count is deferred to the pagination step below.
        if not has_pagination_params:
            self.record_count = queryset.count()

        should_paginate = (
            has_pagination_params or self.record_count > retrieval_threshold
        )

        if should_paginate:
            if "page_size" not in self.request.query_params.keys():
                self.paginator.page_size = retrieval_threshold
            if self.record_count is None:
                self.record_count = queryset.count()
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            headers = self.paginator.generate_link_header(
                self.request, queryset, count=self.record_count
            )
        else:
            serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, headers=headers)
