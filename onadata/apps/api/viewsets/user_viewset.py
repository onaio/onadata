from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.generics import get_object_or_404
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from onadata.libs.serializers.user_serializer import UserSerializer
from onadata.apps.api import permissions
from onadata.libs.utils.timing import last_modified_header, get_date


def is_valid_email(email):
    try:
        validate_email(email)
    except ValidationError:
        return False

    return True


def _search_user(request):
    # needs to be authenticated
    if not request.user.is_authenticated():
        error = {'detail': 'Authentication credentials were not provided.'}
        return Response(data=error,
                        status=status.HTTP_401_UNAUTHORIZED)
    # validate email
    if not is_valid_email(request.GET.get('email')):
        return Response(data={'detail': 'Invalid email'},
                        status=status.HTTP_400_BAD_REQUEST)
    # search user using email
    users = User.objects.filter(email=request.GET.get('email'))
    if users:
        serializer = UserSerializer(users[0])
        return Response(serializer.data)
    else:
        return Response(data={'detail': 'User not found'},
                        status=status.HTTP_404_NOT_FOUND)


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


## Search for a users using email
> Example
>
>       curl -X GET https://ona.io/api/v1/users?email=demo@email.com

> Response:

>       {
>           "username": "demo",
>           "first_name": "First",
>           "last_name": "Last"
>       }

"""
    queryset = User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    default_response_headers = last_modified_header(
        get_date(User.objects.last(), 'joined'))
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.DjangoObjectPermissionsAllowAnon]

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

    def list(self, request, *args, **kwargs):
        if request.GET.get('email'):
            return _search_user(request)
        else:
            return super(UserViewSet, self).list(request, *args, **kwargs)
