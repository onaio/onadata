from rest_framework.viewsets import ModelViewSet

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.libs.serializers.textit_serializer import TextItSerializer
from onadata.apps.main.models import MetaData
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.serializers.restservices_serializer import \
    RestServiceSerializer
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.utils.common_tags import TEXTIT
from onadata.apps.api.tools import get_baseviewset_class


BaseViewset = get_baseviewset_class()


class RestServicesViewSet(AuthenticateHeaderMixin,
                          CacheControlMixin, LastModifiedMixin, BaseViewset,
                          ModelViewSet):
    """
    This endpoint provides access to form rest services.
    """
    queryset = RestService.objects.select_related('xform')
    serializer_class = RestServiceSerializer
    permission_classes = [MetaDataObjectPermissions, ]
    filter_backends = (filters.MetaDataFilter, )

    def get_serializer_class(self):
        name = self.request.DATA.get('name')

        if name == TEXTIT:
            return TextItSerializer

        return super(RestServicesViewSet, self).get_serializer_class()

    def post_delete(self, obj):
        if obj.name == TEXTIT:
            MetaData.objects.filter(
                xform=obj.xform, data_type=obj.name).delete()
