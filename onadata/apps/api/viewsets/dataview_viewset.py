from rest_framework.viewsets import ModelViewSet

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.permissions import XFormPermissions
from onadata.libs.serializers.dataview_serializer import DataViewSerializer


class DataViewViewSet(ModelViewSet):
    """
    A simple ViewSet for viewing and editing DataViews.
    """
    queryset = DataView.objects.select_related()
    serializer_class = DataViewSerializer
    permission_classes = [XFormPermissions]
