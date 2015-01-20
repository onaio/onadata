from django.conf import settings

from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.user_profile_serializer import\
    UserProfileSerializer
from onadata.apps.main.models import UserProfile
from onadata.apps.api.permissions import UserProfilePermissions


class UserProfileViewSet(LastModifiedMixin, ObjectLookupMixin, ModelViewSet):

    """
List, Retrieve, Update, Create/Register users.

## Register a new User
`username, email, firstname` Are required fields. \n
`username` is alphanumeric
<pre class="prettyprint"><b>POST</b> /api/v1/profiles</pre>
> Example
>
>        {
>            "username": "demo",
>            "first_name": "Demo",
>            "last_name": "User",
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
>            "first_name": "Demo",
>            "last_name": "User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"
>            "metadata": {},
>            "joined_on": "2014-11-10T14:22:20.394Z"
>        },
>        {
>           ...}, ...
>       ]

## Retrieve User Profile Information

<pre class="prettyprint"><b>GET</b> /api/v1/profiles/{username}</pre>
<pre class="prettyprint"><b>GET</b> /api/v1/profiles/{pk}</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/profiles/demo

> Response
>
>        {
>            "url": "https://ona.io/api/v1/profiles/demo",
>            "username": "demo",
>            "first_name": "Demo",
>            "last_name": "User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"
>            "metadata": {},
>            "joined_on": "2014-11-10T14:22:20.394Z"

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
>            "first_name": "Demo",
>            "last_name": "User",
>            "email": "demo@localhost.com",
>            "city": "",
>            "country": "KE",
>            "organization": "",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/demo"
>            "metadata": {},
>            "joined_on": "2014-11-10T14:22:20.394Z"
>        }

## Change authenticated user's password
> Example
>
>       curl -X POST -d current_password=password1 -d new_password=password2\
 https://ona.io/api/v1/profile/demouser/change_password
> Response:
>
>        HTTP 200 OK
"""
    queryset = UserProfile.objects.exclude(user__pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserProfileSerializer
    lookup_field = 'user'
    permission_classes = [UserProfilePermissions]
    ordering = ('user__username', )

    def get_object(self, queryset=None):
        """Lookup user profile by pk or username"""
        if self.kwargs.get(self.lookup_field, None) is None:
            raise ParseError(
                'Expected URL keyword argument `%s`.' % self.lookup_field
            )
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer()
        lookup_field = self.lookup_field

        if self.lookup_field in serializer.get_fields():
            k = serializer.get_fields()[self.lookup_field]
            if isinstance(k, serializers.HyperlinkedRelatedField):
                lookup_field = '%s__%s' % (self.lookup_field, k.lookup_field)

        lookup = self.kwargs[self.lookup_field]
        filter_kwargs = {lookup_field: lookup}

        try:
            pk = int(lookup)
        except (TypeError, ValueError):
            pass
        else:
            filter_kwargs = {'user__pk': pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    @action(methods=['POST'])
    def change_password(self, request, *args, **kwargs):
        user_profile = self.get_object()
        current_password = request.DATA.get('current_password', None)
        new_password = request.DATA.get('new_password', None)

        if new_password:
            if user_profile.user.check_password(current_password):
                user_profile.user.set_password(new_password)
                user_profile.user.save()

                return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_400_BAD_REQUEST)
