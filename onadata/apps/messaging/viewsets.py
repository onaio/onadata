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

    def list(self, request, *args, **kwargs):
        headers = None
        queryset = self.filter_queryset(self.get_queryset())
        retrieval_threshold = getattr(settings, "MESSAGE_RETRIEVAL_THRESHOLD", 100)
        pagination_keys = [
            self.paginator.page_query_param,
            self.paginator.page_size_query_param,
        ]
        query_param_keys = self.request.query_params
        has_pagination_params = any(k in query_param_keys for k in pagination_keys)

        # Once record_count is set, pagination and the Link header do not
        # trigger extra COUNT(*) queries.
        record_count = None

        if not has_pagination_params:
            record_count = queryset.count()

        should_paginate = has_pagination_params or record_count > retrieval_threshold

        if should_paginate:
            if "page_size" not in self.request.query_params.keys():
                self.paginator.page_size = retrieval_threshold
            if record_count is None:
                record_count = queryset.count()
            page = self.paginator.paginate_queryset(
                queryset, self.request, view=self, count=record_count
            )
            serializer = self.get_serializer(page, many=True)
            headers = self.paginator.generate_link_header(
                self.request, queryset, count=record_count
            )
        else:
            serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, headers=headers)
