from rest_framework import serializers
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.api_export_tools import (EXPORT_FAILED,
                                                 EXPORT_SUCCESS,
                                                 EXPORT_PENDING)


class ExportSerializer(serializers.HyperlinkedModelSerializer):
    job_status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = Export
        fields = ('id', 'job_status', 'type', 'task_id', 'xform')

    def get_job_status(self, obj):
        if obj.internal_status == Export.PENDING:
            return EXPORT_PENDING
        elif obj.internal_status == Export.SUCCESSFUL:
            return EXPORT_SUCCESS
        else:
            return EXPORT_FAILED

    def get_type(self, obj):
        return obj.export_type
