from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.serializers.restservices_serializer import \
    RestServiceSerializer
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin


class RestServicesViewSet(LastModifiedMixin, ModelViewSet):
    """
    This endpoint provides access to form restservices.
    """
    queryset = RestService.objects.select_related('xform')
    serializer_class = RestServiceSerializer
    permission_classes = [MetaDataObjectPermissions, ]
    filter_backends = (filters.MetaDataFilter, )
