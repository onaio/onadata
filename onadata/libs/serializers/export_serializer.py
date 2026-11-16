# -*- coding: utf-8 -*-
"""
The ExportSerializer class - create, list exports.
"""
from functools import cached_property, lru_cache

from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.viewer.models.export import Export
from onadata.libs.permissions import (
    can_read_all_xform_data,
    export_dataview_query_string,
)
from onadata.libs.utils.async_status import status_msg


class ExportSerializer(serializers.HyperlinkedModelSerializer):
    """
    The ExportSerializer class - create, list exports.
    """

    date_created = serializers.ReadOnlyField(source="created_on")
    job_status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    export_url = serializers.SerializerMethodField()

    class Meta:
        model = Export
        fields = (
            "id",
            "job_status",
            "type",
            "task_id",
            "xform",
            "date_created",
            "filename",
            "options",
            "export_url",
            "error_message",
        )

    def get_job_status(self, obj):
        """Returns export async status text."""
        return status_msg.get(obj.internal_status)

    def get_type(self, obj):
        """Returns export type - CSV,XLS,..."""
        return obj.export_type

    @cached_property
    def _can_read_all_data(self):
        """Checks each form once, because a form can have many dataview exports."""
        return lru_cache(maxsize=None)(can_read_all_xform_data)

    def get_export_url(self, obj):
        """Returns the export download URL."""
        if obj.export_url:
            return obj.export_url

        request = self.context.get("request")
        if request:
            return reverse(
                "export-detail",
                kwargs={"pk": obj.pk},
                request=request,
                format=obj.export_type.replace("_", ""),
            ) + export_dataview_query_string(request.user, obj, self._can_read_all_data)

        return None
