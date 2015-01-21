from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.decorators import list_route
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from django.utils.translation import ugettext as _

from onadata.apps.api.permissions import ConnectViewsetPermissions
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.serializers.password_reset_serializer import \
    PasswordResetSerializer, PasswordResetChangeSerializer
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.serializers.user_profile_serializer import (
    UserProfileWithTokenSerializer)

from onadata.settings.common import DEFAULT_SESSION_EXPIRY_TIME
from onadata.apps.api.models.temp_token import TempToken


class ConnectViewSet(LastModifiedMixin,
                     ObjectLookupMixin,
                     viewsets.GenericViewSet):

    """This endpoint allows you retrieve the authenticated user's profile info.

# Retrieve profile
> Example
>
>       curl -X GET https://ona.io/api/v1/user

> Response:

>       {
            "api_token": "76121138a080c5ae94f318a8b9be91e7ebebb484",
            "temp_token": "0668993ad2f9fa6a0bff58389996cf85f11894ca"
            "city": "Nairobi",
            "country": "Kenya",
            "gravatar": "avatar.png",
            "name": "Demo User",
            "email": "demo@user.com",
            "organization": "",
            "require_auth": false,
            "twitter": "",
            "url": "http://localhost:8000/api/v1/profiles/demo",
            "user": "http://localhost:8000/api/v1/users/demo",
            "username": "demo",
            "website": "",
}

# Get projects that the authenticating user has starred
<pre class="prettyprint">
<b>GET</b> /api/v1/user/<code>{username}</code>/starred</pre>

# Request password reset
<pre class="prettyprint">
<b>POST</b> /api/v1/user/reset
</pre>

- Sends an email to the user's email with a url that \
redirects to a reset password form on the API consumer's website.
- `email` and `reset_url` are expected in the POST payload.
- Expected reset_url format is `reset_url=https:/domain/path/to/reset/form`.
- Example of reset url sent to user's email is\
`http://mydomain.com/reset_form?uid=Mg&token=2f3f334g3r3434&username=dXNlcg==`.
- `uid` is the users `unique key` which is a base64 encoded integer value that\
 can be used to access the users info at `/api/v1/users/<pk>` or \
`/api/v1/profiles/<pk>`. You can retrieve the integer value in `javascript` \
using the `window.atob();` function.
`username` is a base64 encoded value of the user's username
- `token` is a onetime use token that allows password reset

>
> Example
>
>       curl -X POST -d email=demouser@mail.com\
 -d reset_url=http://example-url.com/reset https://ona.io/api/v1/user/reset
>
> Response:
>
>        HTTP 204 OK


>
# Reset user password
<pre class="prettyprint">
<b>POST</b> /api/v1/user/reset
</pre>

- Resets user's password
- `uid`, `token` and `new_password` are expected in the POST payload.
- minimum password length is 4 characters

>
> Example
>
>       curl -X POST -d uid=Mg -d token=qndoi209jf02n4 \
-d new_password=usernewpass https://ona.io/api/v1/user/reset
>
> Response:
>
>        HTTP 204 OK
>
# Expire temporary token
<pre class="prettyprint">
<b>DELETE</b> /api/v1/user/expire
</pre>

- Expires the temporary token

>
> Example
>
>       curl -X DELETE https://ona.io/api/v1/user/expire \
-u <username>:<password>
>
> Response:
>
>        HTTP 204 OK
>

"""
    lookup_field = 'user'
    queryset = UserProfile.objects.all()
    permission_classes = (ConnectViewsetPermissions,)
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
        projects = user.project_stars.all()
        serializer = ProjectSerializer(projects,
                                       context={'request': request},
                                       many=True)

        return Response(data=serializer.data)

    @list_route(methods=['POST'])
    def reset(self, request, *args, **kwargs):
        context = {'request': request}
        data = request.DATA if request.DATA is not None else {}
        if 'token' in request.DATA:
            serializer = PasswordResetChangeSerializer(data=data,
                                                       context=context)
        else:
            serializer = PasswordResetSerializer(data=data, context=context)

        if serializer.is_valid():
            serializer.save()

            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @list_route(methods=['DELETE'])
    def expire(self, request, *args, **kwargs):
        try:
            TempToken.objects.get(user=request.user).delete()
        except TempToken.DoesNotExist:
            raise ParseError(_(u"Temporary token not found!"))

        return Response(status=status.HTTP_204_NO_CONTENT)
