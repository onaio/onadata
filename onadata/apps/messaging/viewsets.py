# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""

from __future__ import unicode_literals

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
    # count of the filtered queryset for the current request, reused across
    # pagination and Link header generation to avoid repeat COUNT(*)
    record_count = None

    def paginate_queryset(self, queryset):
        """Returns a paginated queryset"""
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(
            queryset, self.request, view=self, count=self.record_count
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        self.record_count = queryset.count()
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        headers = self.paginator.generate_link_header(
            self.request, queryset, count=self.record_count
        )
        return Response(serializer.data, headers=headers)
