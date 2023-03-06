"""
API Endpoint implementation for Messaging statistics
"""
import json

from django.db.models import Count
from django.http import StreamingHttpResponse
from django.utils.translation import gettext as _

from actstream.models import Action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from onadata.apps.messaging.constants import MESSAGE_VERBS
from onadata.apps.messaging.filters import (
    ActionFilterSet,
    TargetIDFilterBackend,
    TargetTypeFilterBackend,
)
from onadata.apps.messaging.permissions import TargetObjectPermissions


class MessagingStatsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Provides a count of each unique messaging event grouped by either day, month
    or year.

    The endpoint accepts the following query parameters:

    - `group_by`: field specifying whether to group events by `day`, `month` or `year`
    - `target_type`: field to be used to determine the target
       object type i.e xform, project
    - `target_id`: field used to identify the target object
    - `verb`: field used to filter returned responses by a specific verb
    - `timestamp`: used to filter by actions that occurred in a specific timeframe.
       This query parameter support date time lookups
       i.e `timestamp__day`, `timestamp__year

    Example:

    `GET /api/v1/stats/messaging?target_id=1&target_type=xform&group_by=day`

    Response:
    ```json
    [
        {
            "submission_edited": 10,
            "submission_created": 5,
            "submission_deleted": 15,
            "group": "2023-02-17"
        }
    ]
    ```
    """

    SUPPORTED_GROUP_BY = {"day": "YYYY-MM-DD", "month": "MM-YYYY", "year": "YYYY"}

    queryset = Action.objects.filter(verb__in=MESSAGE_VERBS)
    permission_classes = [IsAuthenticated, TargetObjectPermissions]
    filter_backends = [
        TargetTypeFilterBackend,
        TargetIDFilterBackend,
        DjangoFilterBackend,
    ]
    filterset_class = ActionFilterSet

    def _stream_annotated_queryset(self, queryset):
        yield "["
        group = None
        prev_group = None
        out = {}
        for item in queryset.iterator():
            if group is None:
                group = item.get("group")
            elif group != item.get("group"):
                yield json.dumps(out)
                yield ","
                prev_group = group
                out = {}
                group = item.get("group")

            out["group"] = group
            verb = item.get("verb")
            out[verb] = item.get("count")
        if prev_group != group:
            yield json.dumps(out)
        yield "]"

    def _generate_annotated_queryset(self, request, queryset):
        field = request.query_params.get("group_by")
        if field is None:
            raise exceptions.ParseError(_("Parameter 'group_by' is missing."))

        if field not in self.SUPPORTED_GROUP_BY:
            raise exceptions.ParseError(_("Parameter 'group_by' is not valid."))

        group_format = self.SUPPORTED_GROUP_BY[field]
        return (
            queryset.extra(select={"group": f"TO_CHAR(timestamp, '{group_format}')"})
            .values("group", "verb")
            .order_by("-group")
            .annotate(count=Count("verb"))
        )

    def list(
        self, request, *args, **kwargs
    ):  # noqa pylint: disable=missing-function-docstring
        queryset = self._generate_annotated_queryset(
            request, self.filter_queryset(self.get_queryset())
        )
        rsp = StreamingHttpResponse(  # noqa pylint: disable=http-response-with-content-type-json
            self._stream_annotated_queryset(queryset), content_type="application/json"
        )
        return rsp
