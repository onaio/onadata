
from rest_framework.viewsets import ModelViewSet

from onadata.apps.logger.models.widget import Widget
from onadata.libs.serializers.widget_serilizer import WidgetSerializer
from onadata.apps.api.permissions import WidgetViewSetPermissions

class WidgetViewSet(ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = 'pk'
