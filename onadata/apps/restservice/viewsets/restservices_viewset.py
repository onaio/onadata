from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework import status

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.serializers.restservices_serializer import \
    RestServiceSerializer
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.apps.main.models.meta_data import MetaData


class RestServicesViewSet(LastModifiedMixin, ModelViewSet):
    """
    This endpoint provides access to form rest services.
    """
    queryset = RestService.objects.select_related('xform')
    serializer_class = RestServiceSerializer
    permission_classes = [MetaDataObjectPermissions, ]
    filter_backends = (filters.MetaDataFilter, )

    @detail_route(methods=['POST', 'GET', 'DELETE'])
    def textit(self, request, *args, **kwargs):
        """
        This action enable one to set auth_token, flow_uuid and the contact to
        be used with textit

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        self.object = self.get_object()

        if request.method == 'GET':
            meta = MetaData.textit(self.object.xform)
            serializer = MetaDataSerializer(meta,
                                            context={'request': request})
            return Response(serializer.data)
        elif request.method == 'POST':
            auth_token = request.DATA.get('auth_token')
            flow_uuid = request.DATA.get('flow_uuid')
            contacts = request.DATA.get("contacts")

            data = {
                'xform': self.object.xform.pk,
                'data_type': 'textit',
                'data_value': '{}|{}|{}'.format(auth_token,
                                                flow_uuid,
                                                contacts)
            }
            serializer = MetaDataSerializer(data=data,
                                            context={'request': request})

            if serializer.is_valid():
                serializer.save()
            else:
                return Response(data=serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

            return Response(data=serializer.data,
                            status=status.HTTP_201_CREATED)

        else:
            # delete
            meta = MetaData.textit(self.object.xform)
            meta.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
