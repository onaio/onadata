# -*- coding: utf-8 -*-
"""
Messaging /messaging viewsets.
"""

from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Max
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from actstream.models import Action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from onadata.apps.messaging.constants import MESSAGE_VERBS
from onadata.apps.messaging.filters import (
    ActionFilterSet,
    TargetIDFilterBackend,
    TargetTypeFilterBackend,
    UserFilterBackend,
)
from onadata.apps.messaging.permissions import TargetObjectPermissions
from onadata.apps.messaging.serializers import (
    GroupedActivitySerializer,
    MessageSerializer,
)
from onadata.libs.pagination import StandardPageNumberPagination

User = get_user_model()


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
    pagination_class = StandardPageNumberPagination

    # Grouping dimensions the ``group_by`` param accepts, mapped to the
    # Action column they aggregate on.
    GROUP_BY_FIELDS = {"user": "actor_object_id", "verb": "verb"}

    def list(self, request, *args, **kwargs):
        requested = request.query_params.getlist("group_by")

        if not requested:
            return super().list(request, *args, **kwargs)

        for value in requested:
            if value not in self.GROUP_BY_FIELDS:
                raise exceptions.ParseError(f"Unsupported group_by value '{value}'")

        # Canonical, de-duplicated dimension list (order is stable regardless
        # of the order the params were supplied in).
        dimensions = [dim for dim in self.GROUP_BY_FIELDS if dim in requested]
        db_fields = [self.GROUP_BY_FIELDS[dim] for dim in dimensions]

        user_content_type = ContentType.objects.get_for_model(User)
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(actor_content_type=user_content_type)
            .values(*db_fields)
            .annotate(count=Count("id"), latest=Max("timestamp"))
            .order_by("-latest")
        )
        page = self.paginate_queryset(queryset)

        rows = self._build_grouped_rows(page, dimensions)
        serializer = GroupedActivitySerializer(
            rows, many=True, context={"dimensions": dimensions}
        )

        return self.get_paginated_response(serializer.data)

    def _build_grouped_rows(self, page, dimensions):
        """Shape aggregate rows into the requested grouping dimensions."""
        usernames = {}
        if "user" in dimensions:
            # Resolve actor ids to usernames for the current page in a single
            # query; a row whose actor id no longer resolves to a user (e.g. a
            # dangling reference) keeps a null user.
            actor_ids = {row["actor_object_id"] for row in page}
            usernames = dict(
                User.objects.filter(pk__in=actor_ids).values_list("pk", "username")
            )

        rows = []
        for row in page:
            item = {"count": row["count"], "latest_timestamp": row["latest"]}
            if "user" in dimensions:
                item["user"] = usernames.get(int(row["actor_object_id"]))
            if "verb" in dimensions:
                item["verb"] = row["verb"]
            rows.append(item)

        return rows
