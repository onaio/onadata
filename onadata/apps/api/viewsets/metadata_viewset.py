from rest_framework import viewsets

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer


class MetaDataViewSet(viewsets.ModelViewSet):
    model = MetaData
    serializer_class = MetaDataSerializer
    permissions = (MetaDataObjectPermissions,)
