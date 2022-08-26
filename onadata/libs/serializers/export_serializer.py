# -*- coding: utf-8 -*-
"""
The ExportSerializer class - create, list exports.
"""
from rest_framework import serializers
from rest_framework.reverse import reverse

from onadata.apps.viewer.models.export import Export
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
            )

        return None
