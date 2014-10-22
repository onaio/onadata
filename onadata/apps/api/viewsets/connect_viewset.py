from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.user_profile_serializer import (
    UserProfileSerializer,
    UserProfileWithTokenSerializer)
from onadata.apps.api.permissions import UserProfilePermissions
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
> <pre class="prettyprint">
> <b>GET</b> /api/v1/user/<code>{username}</code>/starred</pre>

## Change authenticated user's password

> Example
>
>       curl -X POST -d current_password=password1 -d new_password=password2\
 https://ona.io/api/v1/user/demouser/change_password
> Response:
>
>        HTTP 200 OK

## Request to reset user's password

> Example
>
>       curl -X GET https://ona.io/api/v1/user/demouser/reset_password
> Response:
>
>        {reset-token: qndoi209jf02n4}

## Reset user's password

> Example
>
>       curl -X POST -d new_password=newpass -d rest-token=qndoi209jf02n4\
 https://ona.io/api/v1/user/demouser/reset_password
> Response:
>
>        HTTP 200 OK
"""
    lookup_field = 'user'
    queryset = UserProfile.objects.all()
    permission_classes = (UserProfilePermissions,)
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

    @action(methods=['POST'])
    def change_password(self, request, *args, **kwargs):
        user_profile = self.get_object()
        attrs = request.DATA
        current_password = attrs.get('current_password', None)
        new_password = attrs.get('new_password', None)
        if new_password:
            if user_profile.user.check_password(current_password):
                user_profile.user.set_password(new_password)
                user_profile.user.save()
                return Response(status=status.HTTP_200_OK)
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET', 'POST'])
    def reset_password(self, request, *args, **kwargs):

        user_profile = self.get_object()

        if request.method == 'GET':
            reset_context = UserProfile.generate_reset_password_token(user_profile.user)
            return Response(status=status.HTTP_200_OK, data=reset_context)
        elif request.user == 'POST':
            return Response()
