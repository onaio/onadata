from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.user_profile_serializer import (
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
>        { token: qndoi209jf02n4
>          uid: erIORE
>        }

## Reset user's password

> Example
>
>       curl -X POST -d token=qndoi209jf02n4 -d uid=erIORE\
 -d new_password=newpass https://ona.io/api/v1/user/demouser/reset_password
> Response:
>
>        HTTP 200 OK
"""
    lookup_field = 'user'
    queryset = UserProfile.objects.all()
    permission_classes = [UserProfilePermissions]
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

        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET', 'POST'])
    def reset_password(self, request, *args, **kwargs):

        UserModel = get_user_model()
        username = self.kwargs['user']
        user = UserModel.objects.get(username__iexact=username)

        if request.method == 'GET':
            data = {'token': default_token_generator.make_token(user),
                    'uid': urlsafe_base64_encode(force_bytes(user.pk))}

            return Response(status=status.HTTP_200_OK, data=data)

        elif request.method == 'POST':
            attrs = request.DATA
            token = attrs.get('token', None)
            uidb64 = attrs.get('uid', None)
            new_password = attrs.get('new_password', None)

            try:
                uid = urlsafe_base64_decode(uidb64)
                user = UserModel._default_manager.get(pk=uid)
            except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
                user = None

            valid_token = default_token_generator.check_token(user, token)

            if user is not None and valid_token and new_password:
                user.set_password(new_password)
                user.save()

                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)
