from rest_framework import serializers

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.async_status import status_msg


class ExportSerializer(serializers.HyperlinkedModelSerializer):
    date_created = serializers.ReadOnlyField(source='created_on')
    job_status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = Export
        fields = ('id', 'job_status', 'type', 'task_id', 'xform',
                  'date_created', 'filename', 'options')

    def get_job_status(self, obj):
        return status_msg.get(obj.internal_status)

    def get_type(self, obj):
        return obj.export_type
