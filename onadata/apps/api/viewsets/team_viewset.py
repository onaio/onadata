from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import exceptions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from onadata.libs.serializers.team_serializer import TeamSerializer
from onadata.apps.api.models import Team
from onadata.apps.api.tools import add_user_to_team, remove_user_from_team


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
>                "organization": "bruize",
>                "projects": []
>            },
>            {
>                "url": "https://ona.io/api/v1/teams/bruize/2",
>                "name": "demo team",
>                "organization": "bruize",
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
>            "organization": "bruize",
>            "projects": []
>        }

## List members of a team

A list of usernames is the response for members of the team.

<pre class="prettyprint">
<b>GET</b> /api/v1/teams/<code>{org}</code>/<code>{pk}/members</code>
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/teams/bruize/1/members

> Response
>
>       ["member1"]
>

## Add a user to a team

POST `{"username": "someusername"}`
to `/api/v1/teams/<owner|org>/<team id|team name>/members` to add a user to
the specified team.
A list of usernames is the response for members of the team.

<pre class="prettyprint">
<b>POST</b> /api/v1/teams/<code>{org}</code>/<code>{pk}/members</code>
</pre>

> Response
>
>       ["someusername"]

"""
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
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
        owner = self.kwargs['owner']
        pk = self.kwargs['pk']
        q_filter = {
            'organization__username__iexact': owner,
        }

        try:
            pk = int(pk)
        except ValueError:
            q_filter['name__iexact'] = u'%s#%s' % (owner, pk)
        else:
            q_filter['pk'] = pk

        qs = self.filter_queryset(self.get_queryset())

        return get_object_or_404(qs, **q_filter)

    def list(self, request, **kwargs):
        filter = {}
        if 'owner' in kwargs:
            filter['organization__username'] = kwargs['owner']
        qs = self.filter_queryset(self.get_queryset())
        self.object_list = qs.filter(**filter)
        serializer = self.get_serializer(self.object_list, many=True)
        return Response(serializer.data)

    @action(methods=['GET', 'POST'])
    def members(self, request, *args, **kwargs):
        team = self.get_object()
        data = {}
        status_code = status.HTTP_200_OK

        if request.method in ['DELETE', 'POST']:
            username = request.DATA.get('username') or\
                request.QUERY_PARAMS.get('username')

            if username:
                try:
                    user = User.objects.get(username__iexact=username)
                except User.DoesNotExist:
                    status_code = status.HTTP_400_BAD_REQUEST
                    data['username'] = [
                        _(u"User `%(username)s` does not exist."
                          % {'username': username})]
                else:
                    if request.method == 'POST':
                        add_user_to_team(team, user)
                    elif request.method == 'DELETE':
                        remove_user_from_team(team, user)
                    status_code = status.HTTP_201_CREATED
            else:
                status_code = status.HTTP_400_BAD_REQUEST
                data['username'] = [_(u"This field is required.")]

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            data = [u.username for u in team.user_set.all()]

        return Response(data, status=status_code)
