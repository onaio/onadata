from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.libs.serializers.user_serializer import UserSerializer
from onadata.apps.api import permissions


class UserViewSet(ReadOnlyModelViewSet):
    """
This endpoint allows you to list and retrieve user's first and last names.

## List Users
> Example
>
>       curl -X GET https://ona.io/api/v1/users

> Response:

>       [
>            {
>                "username": "demo",
>                "first_name": "First",
>                "last_name": "Last"
>            },
>            {
>                "username": "another_demo",
>                "first_name": "Another",
>                "last_name": "Demo"
>            },
>            ...
>        ]


## Retrieve a specific user info

<pre class="prettyprint"><b>GET</b> /api/v1/users/{username}</pre>

> Example:
>
>        curl -X GET https://ona.io/api/v1/users/demo

> Response:
>
>       {
>           "username": "demo",
>           "first_name": "First",
>           "last_name": "Last"
>       }

"""
    queryset = User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.DjangoObjectPermissionsAllowAnon]
