# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""
from __future__ import unicode_literals

from django.conf import settings
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
from onadata.libs.pagination import StandardPageNumberPagination


# pylint: disable=too-many-ancestors
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
    pagination_class = StandardPageNumberPagination

    def list(self, request, *args, **kwargs):
        headers = None
        queryset = self.filter_queryset(self.get_queryset())
        no_of_records = queryset.count()
        retrieval_threshold = getattr(settings, "MESSAGE_RETRIEVAL_THRESHOLD", 10000)
        pagination_keys = [
            self.paginator.page_query_param,
            self.paginator.page_size_query_param,
        ]
        query_param_keys = self.request.query_params
        should_paginate = (
            any(k in query_param_keys for k in pagination_keys)
            or no_of_records > retrieval_threshold
        )

        if should_paginate and "page_size" not in self.request.query_params.keys():
            self.paginator.page_size = retrieval_threshold

        if should_paginate:
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            headers = self.paginator.generate_link_header(self.request, queryset)
        else:
            serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, headers=headers)
