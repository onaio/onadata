from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from api import serializers


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
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.DjangoModelPermissions, ]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return User.objects.filter(
            Q(pk__in=user.userprofile_set.values('user')) | Q(pk=user.pk))
