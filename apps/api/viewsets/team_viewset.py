from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.api import serializers
from apps.api.models import Team


class TeamViewSet(ModelViewSet):
    """
This endpoint allows you to create, update and view team information.

## GET List of Teams within an Organization.
Provides a json list of teams within a specified organization
 and the projects the team is assigned to, where:

* `org` - is the unique organization name identifier

<pre class="prettyprint">
<b>GET</b> /api/v1/teams
<b>GET</b> /api/v1/teams/<code>{org}</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/teams/bruize

> Response
>
>        [
>            {
>                "url": "https://ona.io/api/v1/teams/bruize/1",
>                "name": "Owners",
>                "organization": "https://ona.io/api/v1/users/bruize",
>                "projects": []
>            },
>            {
>                "url": "https://ona.io/api/v1/teams/bruize/2",
>                "name": "demo team",
>                "organization": "https://ona.io/api/v1/users/bruize",
>                "projects": []
>            }
>        ]

## GET Team Info for a specific team.

Shows teams details and the projects the team is assigned to, where:

* `org` - is the unique organization name identifier
* `pk` - unique identifier for the team

<pre class="prettyprint">
<b>GET</b> /api/v1/teams/<code>{org}</code>/<code>{pk}</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/teams/bruize/1

> Response
>
>        {
>            "url": "https://ona.io/api/v1/teams/bruize/1",
>            "name": "Owners",
>            "organization": "https://ona.io/api/v1/users/bruize",
>            "projects": []
>        }
"""
    queryset = Team.objects.all()
    serializer_class = serializers.TeamSerializer
    lookup_fields = ('owner', 'pk')
    lookup_field = 'owner'
    extra_lookup_fields = None

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        orgs = user.organizationprofile_set.values('user')
        return Team.objects.filter(organization__in=orgs)

    def get_object(self):
        if 'owner' not in self.kwargs and 'pk' not in self.kwargs:
            raise exceptions.ParseError(
                'Expected URL keyword argument `owner` and `pk`.'
            )
        filter = {
            'organization__username': self.kwargs['owner'],
            'pk': self.kwargs['pk']
        }
        qs = self.filter_queryset(self.get_queryset())
        return get_object_or_404(qs, **filter)

    def list(self, request, **kwargs):
        filter = {}
        if 'owner' in kwargs:
            filter['organization__username'] = kwargs['owner']
        qs = self.filter_queryset(self.get_queryset())
        self.object_list = qs.filter(**filter)
        serializer = self.get_serializer(self.object_list, many=True)
        return Response(serializer.data)
