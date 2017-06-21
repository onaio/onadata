from rest_framework import serializers

from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.async_status import status_msg

from rest_framework.reverse import reverse


class ExportSerializer(serializers.HyperlinkedModelSerializer):
    date_created = serializers.ReadOnlyField(source='created_on')
    job_status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    export_url = serializers.SerializerMethodField()

    class Meta:
        model = Export
        fields = ('id', 'job_status', 'type', 'task_id', 'xform',
                  'date_created', 'filename', 'options', 'export_url')

    def get_job_status(self, obj):
        return status_msg.get(obj.internal_status)

    def get_type(self, obj):
        return obj.export_type

    def get_export_url(self, obj):
        if obj.export_url:
            return obj.export_url

        request = self.context.get('request')
        if request:
            export_url = reverse(
                'export-detail',
                kwargs={'pk': obj.pk},
                request=request,
                format=obj.export_type.replace('_', '')
            )

            return export_url
