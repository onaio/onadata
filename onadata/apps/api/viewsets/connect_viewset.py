from rest_framework import permissions
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.user_profile_serializer import (
    UserProfileWithTokenSerializer)
from onadata.apps.main.models.user_profile import UserProfile

from onadata.settings.common import DEFAULT_SESSION_EXPIRY_TIME


class ConnectViewSet(ObjectLookupMixin, viewsets.GenericViewSet):

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

## Get projects that the authenticating user has starred
<pre class="prettyprint">
<b>GET</b> /api/v1/user/<code>{username}</code>/starred</pre>
"""
    lookup_field = 'user'
    queryset = UserProfile.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserProfileWithTokenSerializer

    def list(self, request, *args, **kwargs):
        """ Returns authenticated user profile"""

        if request and not request.user.is_anonymous():
            session = getattr(request, "session")
            if not session.session_key:
                # login user to create session token
                # TODO cannot call this without calling authenticate first or
                # setting the backend, commented for now.
                # login(request, request.user)
                session.set_expiry(DEFAULT_SESSION_EXPIRY_TIME)

        serializer = UserProfileWithTokenSerializer(
            instance=request.user.profile,
            context={"request": request})

        return Response(serializer.data)

    @action(methods=['GET'])
    def starred(self, request, *args, **kwargs):
        """Return projects starred for this user."""
        user_profile = self.get_object()
        user = user_profile.user
        projects = user.project_set.all()
        serializer = ProjectSerializer(projects,
                                       context={'request': request},
                                       many=True)

        return Response(data=serializer.data)