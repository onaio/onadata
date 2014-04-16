from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.user_profile_serializer import\
    UserProfileSerializer
from onadata.apps.main.models import UserProfile


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
>        }
"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    lookup_field = 'user'
    permission_classes = [permissions.DjangoModelPermissions, ]
    ordering = ('user__username', )

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return UserProfile.objects.filter(
            Q(user__in=user.userprofile_set.values('user')) | Q(user=user))
