from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.response import Response


from onadata.libs.serializers.user_profile_serializer import (
    UserProfileSerializer)
from onadata.apps.main.models.user_profile import UserProfile


class ConnectViewSet (viewsets.GenericViewSet):

    model = UserProfile
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserProfileSerializer

    def list(self, request, *args, **kwargs):
        """ Returns authenticated user profile"""
        serializer = UserProfileSerializer(instance=request.user.profile,
                                           context={"request": request})
        return Response(serializer.data)
