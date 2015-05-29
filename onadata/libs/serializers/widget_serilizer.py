from rest_framework import serializers

from onadata.apps.logger.models.widget import Widget

class WidgetSerializer(serializers.Serializer):
    class Meta:
        model = Widget
