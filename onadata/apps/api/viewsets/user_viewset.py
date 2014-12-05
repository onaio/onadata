from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.generics import get_object_or_404
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import filters

from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.serializers.user_serializer import UserSerializer
from onadata.apps.api import permissions


class UserViewSet(LastModifiedMixin, ReadOnlyModelViewSet):

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


## Search for a users using email
> Example
>
>       curl -X GET https://ona.io/api/v1/users?search=demo@email.com

> Response:

>        [
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

"""
    queryset = User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.UserViewSetPermissions]
    filter_backends = (filters.SearchFilter,)
    search_fields = ('=email',)
    last_modified_field = 'joined'

    def get_object(self, queryset=None):
        """Lookup a  username by pk else use lookup_field"""
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        lookup = self.kwargs.get(self.lookup_field)
        filter_kwargs = {self.lookup_field: lookup}

        try:
            pk = int(lookup)
        except ValueError:
            pass
        else:
            filter_kwargs = {'pk': pk}

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
