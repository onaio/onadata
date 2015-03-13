from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework import status

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.libs.models.textit_service import TextitService
from onadata.libs.serializers.Textit_serializer import TextItSerializer
from onadata.apps.restservice.models import RestService
from onadata.libs import filters
from onadata.libs.serializers.restservices_serializer import \
    RestServiceSerializer
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin


class RestServicesViewSet(LastModifiedMixin, ModelViewSet):
    """
    This endpoint provides access to form rest services.
    """
    queryset = RestService.objects.select_related('xform')
    serializer_class = RestServiceSerializer
    permission_classes = [MetaDataObjectPermissions, ]
    filter_backends = (filters.MetaDataFilter, )

    @detail_route(methods=['POST', 'GET'])
    def webhook(self, request, *args, **kwargs):
        """
        utility action for the different services

        :param request:
        :param args:
        :param kwargs:
        :return:
        """

        self.object = self.get_object()
        data = request.DATA or request.QUERY_PARAMS
        data = dict(data.items() + [('xform', self.object.xform.pk)])
        if request.method == 'GET':

            if data.get("service") == 'textit':
                if data.get("remove"):
                    instance = TextitService(xform=self.object.xform,
                                             remove=True)
                    instance.save()
                    return Response(status=status.HTTP_204_NO_CONTENT)

                instance = TextitService(xform=self.object.xform)
                instance.retrieve()
                serializer = TextItSerializer(instance=instance)
                return Response(serializer.data)
            else:
                return Response(data={"error": u"Service not yet supported"},
                                status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'POST':

            if data.get("service") == 'textit':
                serializer = TextItSerializer(data=data)

                if serializer.is_valid():
                    serializer.save()
                else:
                    return Response(data=serializer.errors,
                                    status=status.HTTP_400_BAD_REQUEST)

                return Response(data=serializer.data,
                                status=status.HTTP_201_CREATED)
            else:
                return Response(data={"error": "Service not yet supported"},
                                status=status.HTTP_400_BAD_REQUEST)
