from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.user_profile_serializer import\
    UserProfileSerializer
from onadata.apps.main.models import UserProfile
from onadata.apps.api.permissions import UserProfilePermissions


class UserProfileViewSet(ObjectLookupMixin, ModelViewSet):
    """
List, Retrieve, Update, Create/Register users.

## Register a new User
<pre class="prettyprint"><b>POST</b> /api/v1/profiles</pre>
> Example
>
>        {
>            "username": "demo",
>            "name": "Demo User",
>            "email": "demo@localhost.com",
>            "city": "Kisumu",
>            "country": "KE",
>            ...
>        }

## List User Profiles
<pre class="prettyprint"><b>GET</b> /api/v1/profiles</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/profiles

> Response
>
>       [
>        {
>            "url": "https://ona.io/api/v1/profiles/demo",
>            "username": "demo",
>            "name": "Demo User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"
>        },
>        {
>           ...}, ...
>       ]

## Retrieve User Profile Information

<pre class="prettyprint"><b>GET</b> /api/v1/profiles/{username}</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/profiles/demo

> Response
>
>        {
>            "url": "https://ona.io/api/v1/profiles/demo",
>            "username": "demo",
>            "name": "Demo User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"

## Partial updates of User Profile Information

Properties of the UserProfile can be updated using `PATCH` http method.
Payload required is for properties that are to be changed in JSON,
for example, `{"country": "KE"}` will set the country to `KE`.

<pre class="prettyprint"><b>PATCH</b> /api/v1/profiles/{username}</pre>
> Example
>
>     \
curl -X PATCH -d '{"country": "KE"}' https://ona.io/api/v1/profiles/demo \
-H "Content-Type: application/json"

> Response
>
>        {
>            "url": "https://ona.io/api/v1/profiles/demo",
>            "username": "demo",
>            "name": "Demo User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "KE",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"
>        }

## Change authenticated user's password
> Example
>
>       curl -X POST -d current_password=password1 -d new_password=password2\
 https://ona.io/api/v1/profile/demouser/change_password
> Response:
>
>        HTTP 200 OK

## Request to reset user's password

> Example
>
>       curl -X GET https://ona.io/api/v1/profile/demouser/reset_password
> Response:
>
>        { token: qndoi209jf02n4
>          uid: erIORE
>        }

## Reset user's password

> Example
>
>       curl -X POST -d token=qndoi209jf02n4 -d uid=erIORE\
 -d new_password=newpass https://ona.io/api/v1/profile/demouser/reset_password
> Response:
>
>        HTTP 200 OK
"""
    queryset = UserProfile.objects.exclude(user__pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserProfileSerializer
    lookup_field = 'user'
    permission_classes = [UserProfilePermissions]
    ordering = ('user__username', )

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
            except (TypeError, ValueError,
                    OverflowError, UserModel.DoesNotExist):
                user = None

            valid_token = default_token_generator.check_token(user, token)

            if user is not None and valid_token and new_password:
                user.set_password(new_password)
                user.save()

                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)