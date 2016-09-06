from rest_framework import serializers
from onadata.apps.viewer.models.export import Export


class ExportSerializer(serializers.HyperlinkedModelSerializer):
    status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = Export
        fields = ('id', 'status', 'type', 'task_id', 'xform')

    def get_status(self, obj):
        if obj.internal_status == Export.PENDING:
            return 'PENDING'
        elif obj.internal_status == Export.SUCCESSFUL:
            return 'SUCCESSFUL'
        else:
            return 'FAILED'

    def get_type(self, obj):
        return obj.export_type
