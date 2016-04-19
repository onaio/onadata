from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import list_route
from rest_framework.permissions import IsAuthenticated

from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.serializers.google_serializer import \
    GoogleCredentialSerializer


class GoogleViewSet(AuthenticateHeaderMixin,
                    viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, ]

    @list_route()
    def google_auth(self, request, *args, **kwargs):
        data = {
            'code': self.request.GET.get('code')
        }
        serializer = GoogleCredentialSerializer(data=data,
                                                context={
                                                    'request': request
                                                })
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)
