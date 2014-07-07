from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.response import Response


from onadata.libs.serializers.user_profile_serializer import (
    UserProfileWithTokenSerializer)
from onadata.apps.main.models.user_profile import UserProfile


class ConnectViewSet (viewsets.GenericViewSet):

    """This endpoint allows you retrieve the authenticated user's profile info.

## Retrieve profile
> Example
>
>       curl -X GET https://ona.io/api/v1/user

> Response:

>       {
            "api_token": "76121138a080c5ae94f318a8b9be91e7ebebb484",
            "city": "Nairobi",
            "country": "Kenya",
            "gravatar": "avatar.png",
            "name": "Demo User",
            "organization": "",
            "require_auth": false,
            "twitter": "",
            "url": "http://localhost:8000/api/v1/profiles/demo",
            "user": "http://localhost:8000/api/v1/users/demo",
            "username": "demo",
            "website": ""
}

"""
    model = UserProfile
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserProfileWithTokenSerializer

    def list(self, request, *args, **kwargs):
        """ Returns authenticated user profile"""
        serializer = UserProfileWithTokenSerializer(
            instance=request.user.profile,
            context={"request": request})
        return Response(serializer.data)
