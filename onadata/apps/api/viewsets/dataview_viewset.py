from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.api.permissions import DataViewViewsetPermissions

from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.serializers.data_serializer import JsonDataSerializer


class DataViewViewSet(ModelViewSet):
    """
    A simple ViewSet for viewing and editing DataViews.
    """
    queryset = DataView.objects.select_related()
    serializer_class = DataViewSerializer
    permission_classes = [DataViewViewsetPermissions]
    lookup_field = 'pk'

    @action(methods=['GET'])
    def data(self, request, format='json', **kwargs):
        """ Get the data from the xform using this dataview """
        self.object = self.get_object()
        data = DataView.query_data(self.object)
        serializer = JsonDataSerializer(data)

        return Response(serializer.data)
