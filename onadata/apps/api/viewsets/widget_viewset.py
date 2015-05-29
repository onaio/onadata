from rest_framework.permissions import DjangoObjectPermissions
from rest_framework.viewsets import ModelViewSet

from onadata.apps.logger.models.widget import Widget
from onadata.libs.serializers.widget_serilizer import WidgetSerializer

class WidgetViewSet(ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [DjangoObjectPermissions]
    lookup_field = 'pk'
