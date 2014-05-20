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
                                    add_user_to_organization)


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
"""
    queryset = OrganizationProfile.objects.all()
    serializer_class = OrganizationSerializer
    lookup_field = 'user'

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return user.organizationprofile_set.all()

    @action(methods=['GET', 'POST'])
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        status_code = status.HTTP_200_OK
        data = []

        if request.method == 'POST' and 'username' in request.DATA:
            username = request.DATA.get('username')

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                status_code = status.HTTP_400_BAD_REQUEST
                data = {'username':
                        [_(u"User `%(username)s` does not exist."
                           % {'username': username})]}
            else:
                add_user_to_organization(organization, user)
                status_code = status.HTTP_201_CREATED

        elif request.method == 'POST' and 'username' not in request.DATA:
            status_code = status.HTTP_400_BAD_REQUEST
            data = {'username': [_(u"This field is required.")]}

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            members = get_organization_members(organization)
            data = [u.username for u in members]

        return Response(data, status=status_code)
