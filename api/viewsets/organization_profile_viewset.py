from django.contrib.auth.models import User
from rest_framework.viewsets import ModelViewSet

from api import mixins, serializers
from api.models import OrganizationProfile


class OrganizationProfileViewSet(mixins.ObjectLookupMixin, ModelViewSet):
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
    serializer_class = serializers.OrganizationSerializer
    lookup_field = 'user'

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return user.organizationprofile_set.all()
