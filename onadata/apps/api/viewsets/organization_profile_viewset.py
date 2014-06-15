from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.serializers.organization_serializer import(
    OrganizationSerializer)
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import (get_organization_members,
                                    add_user_to_organization,
                                    remove_user_from_organization)


def _try_function_org_username(f, organization, username):
    data = []

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        status_code = status.HTTP_400_BAD_REQUEST
        data = {'username':
                [_(u"User `%(username)s` does not exist."
                   % {'username': username})]}
    else:
        f(organization, user)
        status_code = status.HTTP_201_CREATED

    return [data, status_code]


def _add_username_to_organization(organization, username):
    return _try_function_org_username(add_user_to_organization,
                                      organization,
                                      username)


def _remove_username_to_organization(organization, username):
    return _try_function_org_username(remove_user_from_organization,
                                      organization,
                                      username)


class OrganizationProfileViewSet(ObjectLookupMixin, ModelViewSet):
    """
List, Retrieve, Update, Create/Register Organizations

## Register a new Organization
<pre class="prettyprint"><b>POST</b> /api/v1/orgs</pre>
> Example
>
>        {
>            "org": "modilabs",
>            "name": "Modi Labs Research",
>            "email": "modilabs@localhost.com",
>            "city": "New York",
>            "country": "US",
>            ...
>        }

## List of Organizations
<pre class="prettyprint"><b>GET</b> /api/v1/orgs</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/orgs

> Response
>
>       [
>        {
>            "url": "https://ona.io/api/v1/orgs/modilabs",
>            "org": "modilabs",
>            "name": "Modi Labs Research",
>            "email": "modilabs@localhost.com",
>            "city": "New York",
>            "country": "US",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/modilabs"
>            "creator": "https://ona.io/api/v1/users/demo"
>        },
>        {
>           ...}, ...
>       ]

## Retrieve Organization Profile Information

<pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/orgs/modilabs

> Response
>
>        {
>            "url": "https://ona.io/api/v1/orgs/modilabs",
>            "org": "modilabs",
>            "name": "Modi Labs Research",
>            "email": "modilabs@localhost.com",
>            "city": "New York",
>            "country": "US",
>            "website": "",
>            "twitter": "",
>            "gravatar": "https://secure.gravatar.com/avatar/xxxxxx",
>            "require_auth": false,
>            "user": "https://ona.io/api/v1/users/modilabs"
>            "creator": "https://ona.io/api/v1/users/demo"
>        }

## List Organization members

Get a list of organization members.

<pre class="prettyprint"><b>GET</b> /api/v1/orgs/{username}/members</pre>
> Example
>
>       curl -X GET https://ona.io/api/v1/orgs/modilabs/members

> Response
>
>       ["member1", "member2"]

## Add a user to an organization

To add a user to an organization requires a JSON payload of
`{"username": "member1"}`.

<pre class="prettyprint"><b>POST</b> /api/v1/orgs/{username}/members</pre>
> Example
>
>       curl -X POST -d '{"username": "member1"}' \
https://ona.io/api/v1/orgs/modilabs/members

> Response
>
>       ["member1"]

## Remove a user from an organization

To remove a user from an organization requires a JSON payload of
`{"username": "member1"}`.

<pre class="prettyprint"><b>DELETE</b> /api/v1/orgs/{username}/members</pre>
> Example
>
>       curl -X DELETE -d '{"username": "member1"}' \
https://ona.io/api/v1/orgs/modilabs/members

> Response
>
>       []
"""
    queryset = OrganizationProfile.objects.all()
    serializer_class = OrganizationSerializer
    lookup_field = 'user'

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return user.organizationprofile_set.all()

    @action(methods=['DELETE', 'GET', 'POST'])
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        status_code = status.HTTP_200_OK
        data = []
        username = request.DATA.get('username')

        if request.method in ['DELETE', 'POST'] and not username:
            status_code = status.HTTP_400_BAD_REQUEST
            data = {'username': [_(u"This field is required.")]}
        elif request.method == 'POST':
            data, status_code = _add_username_to_organization(
                organization, username)
        elif request.method == 'DELETE':
            data, status_code = _remove_username_to_organization(
                organization, username)

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            members = get_organization_members(organization)
            data = [u.username for u in members]

        return Response(data, status=status_code)
