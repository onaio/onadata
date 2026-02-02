"""
API Endpoint implementation for Messaging statistics
"""

import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import CharField, Func, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Cast
from django.http import StreamingHttpResponse
from django.utils.translation import gettext as _

from actstream.models import Action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from onadata.apps.messaging.constants import EXPORT_CREATED, MESSAGE_VERBS
from onadata.apps.messaging.filters import (
    ActionFilterSet,
    TargetIDFilterBackend,
    TargetTypeFilterBackend,
)
from onadata.apps.messaging.permissions import TargetObjectPermissions
from onadata.apps.viewer.models.export import ExportBaseModel

logger = logging.getLogger(__name__)


class MessagingStatsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Provides a count of each unique messaging event grouped by either day, month or
    year. Optionally groups by the user who performed the action.

    When include_user=true, the count represents the total number of affected submission
    IDs, not the number of action records.

    Performance: Analyzes the most recent N actions (default 500, configurable via
    MESSAGING_STATS_LIMIT setting).

    Export Type Differentiation: For export_created events, the endpoint
    differentiates between export types (csv, xlsx, etc.) by appending the
    type to the verb. For example, CSV exports appear as "export_created_csv"
    and XLSX exports as "export_created_xlsx".

    The endpoint accepts the following query parameters:

        - `group_by`: field to group events by `day`, `month` or `year`
        - `target_type`: field to be used to determine the target
           object type i.e xform, project
        - `target_id`: field used to identify the target object
        - `include_user`: optional boolean to include user grouping with accurate
           submission counts (default: false)
        - `verb`: field used to filter returned responses by a specific verb
        - `timestamp`: used to filter by actions that occurred in a specific time. This
           query parameter support date time lookups i.e `timestamp__day`,
           `timestamp__year`.

    Example without user grouping:

    `GET /api/v1/stats/messaging?target_id=1&target_type=xform&group_by=day`

    Response:
    ```json
    [
        {
            "group": "2023-02-17",
            "submission_edited": 10,
            "submission_created": 5,
            "submission_deleted": 15,
            "export_created_csv": 3,
            "export_created_xlsx": 2
        }
    ]
    ```

    Example with user grouping:

    GET /api/v1/stats/messaging?target_id=1&target_type=xform&group_by=day
        &include_user=true

    Response:
    ```json
    [
        {
            "group": "2023-02-17",
            "username": "john_doe",
            "submission_edited": 10,
            "submission_created": 57,
            "export_created_csv": 3
        },
        {
            "group": "2023-02-17",
            "username": "jane_smith",
            "submission_deleted": 55,
            "export_created_xlsx": 2
        }
    ]
    ```

    Note: When include_user=true, counts reflect the actual number of submissions
    affected (e.g., 55 submissions deleted), not the number of delete actions (e.g., 3).
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

    @staticmethod
    def _extract_counts_by_export_type(descriptions, verb):
        """
        Extract counts of affected items grouped by export type from descriptions.

        For export_created events, groups counts by export type (e.g., "csv", "xlsx")
        extracted from the description field.

        Args:
            descriptions: List of JSON description strings
            verb: The action verb (e.g., "export_created", "submission_deleted")

        Returns:
            dict: Mapping of export_type -> count. For non-export verbs or exports
                  without type, uses None as the key.
        """
        counts_by_type = {}

        if not descriptions:
            return counts_by_type

        for desc in descriptions:
            if not desc:
                continue

            try:
                parsed = json.loads(desc)
                desc_ids = parsed.get("id", [])

                # Ensure desc_ids is a list
                if not isinstance(desc_ids, list):
                    desc_ids = [desc_ids]

                count = len(desc_ids)

                # For export_created, extract export type from description field
                # Format: {"id": [1, 2], "description": "csv"}
                if verb == EXPORT_CREATED:
                    export_type = None
                    if isinstance(parsed, dict) and "description" in parsed:
                        raw_type = parsed["description"]
                        if raw_type in ExportBaseModel.EXPORT_TYPE_DICT:
                            export_type = raw_type

                    # Group counts by export type
                    counts_by_type[export_type] = (
                        counts_by_type.get(export_type, 0) + count
                    )
                else:
                    # For non-export verbs, use None as key
                    counts_by_type[None] = counts_by_type.get(None, 0) + count
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Failed to parse action description for verb '%s': %s",
                    verb,
                    desc,
                )

        return counts_by_type

    def _stream_annotated_queryset(self, queryset):
        yield "["
        first = True
        group_key = None
        out = {}
        for item in queryset.iterator():
            # Check if user information is included in the results
            if "actor_object_id" in item:
                current_group_key = (item.get("group"), item.get("actor_object_id"))
            else:
                current_group_key = item.get("group")

            if first:
                group_key = current_group_key
                first = False
            elif group_key != current_group_key:
                yield json.dumps(out)
                yield ","
                out = {}
                group_key = current_group_key

            out["group"] = item.get("group")
            # Only include username if it's present
            if "username" in item:
                out["username"] = item.get("username")

            verb = item.get("verb")
            descriptions = item.get("descriptions")

            # Extract counts grouped by export type from descriptions
            counts_by_type = self._extract_counts_by_export_type(descriptions, verb)

            # Add entries for each export type (or single entry for non-export verbs)
            for export_type, count in counts_by_type.items():
                # For export_created, append export type to verb
                # Creates entries like "export_created_csv"
                if verb == EXPORT_CREATED and export_type:
                    verb_key = f"{verb}_{export_type}"
                else:
                    verb_key = verb

                out[verb_key] = count
        if not first:
            yield json.dumps(out)
        yield "]"

    def _generate_annotated_queryset(self, request, queryset):
        field = request.query_params.get("group_by")
        if field is None:
            raise exceptions.ParseError(_("Parameter 'group_by' is missing."))

        if field not in self.SUPPORTED_GROUP_BY:
            raise exceptions.ParseError(_("Parameter 'group_by' is not valid."))

        include_user = (
            request.query_params.get("include_user", "false").lower() == "true"
        )
        group_format = self.SUPPORTED_GROUP_BY[field]

        # Limit to most recent actions for performance (configurable via settings)
        limit = getattr(settings, "MESSAGING_STATS_LIMIT", 500)
        # Use a subquery to keep the limiting operation in the database rather
        # than materializing IDs into Python memory.
        limited_queryset = queryset.filter(
            id__in=Subquery(queryset.values("id")[:limit])
        )

        base_query = limited_queryset.annotate(
            group=Func(
                "timestamp",
                Value(group_format),
                function="TO_CHAR",
                output_field=CharField(),
            )
        )

        if include_user:
            user = get_user_model()
            # Subquery to get username from User model
            # Need to cast actor_object_id to integer since it's stored as varchar
            username_subquery = Subquery(
                user.objects.filter(
                    id=Cast(OuterRef("actor_object_id"), IntegerField())
                ).values("username")[:1]
            )

            return (
                base_query.annotate(username=username_subquery)
                .values("group", "verb", "actor_object_id", "username")
                .order_by("-group", "actor_object_id")
                .annotate(
                    descriptions=ArrayAgg("description", distinct=False),
                )
            )

        return (
            base_query.values("group", "verb")
            .order_by("-group")
            .annotate(
                descriptions=ArrayAgg("description", distinct=False),
            )
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
