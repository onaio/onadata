from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from onadata.apps.api.permissions import RestServiceObjectPermissions
from onadata.libs.serializers.textit_serializer import TextItSerializer
from onadata.libs.serializers.google_serializer import GoogleSheetsSerializer
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.serializers.restservices_serializer import \
    RestServiceSerializer
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.utils.common_tags import TEXTIT, GOOGLESHEET
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
    permission_classes = [RestServiceObjectPermissions, ]
    filter_backends = (filters.RestServiceFilter, )

    def get_serializer_class(self):
        name = self.request.data.get('name')

        if name == TEXTIT:
            return TextItSerializer

        if name == GOOGLESHEET:
            return GoogleSheetsSerializer

        return super(RestServicesViewSet, self).get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.name == TEXTIT:
            serializer = TextItSerializer(instance)
        else:
            serializer = self.get_serializer(instance)

        return Response(serializer.data)

