from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.core.mail import send_mail

from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tools import (get_organization_members,
                                    add_user_to_organization,
                                    remove_user_from_organization,
                                    get_organization_owners_team,
                                    add_user_to_team)
from onadata.apps.api import permissions
from onadata.libs.filters import OrganizationPermissionFilter
from onadata.libs.mixins.last_modified_mixin import LastModifiedMixin
from onadata.libs.mixins.object_lookup_mixin import ObjectLookupMixin
from onadata.libs.permissions import ROLES, OwnerRole
from onadata.libs.serializers.organization_serializer import(
    OrganizationSerializer)
from onadata.settings.common import (DEFAULT_FROM_EMAIL, SHARE_ORG_SUBJECT)


def _try_function_org_username(f, organization, username, args=None):
    data = []

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        status_code = status.HTTP_400_BAD_REQUEST
        data = {'username':
                [_(u"User `%(username)s` does not exist."
                   % {'username': username})]}
    else:
        if args:
            f(organization, user, *args)
        else:
            f(organization, user)
        status_code = status.HTTP_201_CREATED

    return [data, status_code]


def _update_username_role(organization, username, role_cls):
    f = lambda org, user, role_cls: role_cls.add(user, organization)
    return _try_function_org_username(f,
                                      organization,
                                      username,
                                      [role_cls])


def _add_username_to_organization(organization, username):
    return _try_function_org_username(add_user_to_organization,
                                      organization,
                                      username)


def _remove_username_to_organization(organization, username):
    return _try_function_org_username(remove_user_from_organization,
                                      organization,
                                      username)


def _compose_send_email(request, organization, username):
    user = User.objects.get(username=username)

    email_msg = request.DATA.get('email_msg') \
        or request.QUERY_PARAMS.get('email_msg')

    email_subject = request.DATA.get('email_subject') \
        or request.QUERY_PARAMS.get('email_subject')

    if not email_subject:
        email_subject = SHARE_ORG_SUBJECT.format(user.username,
                                                 organization.name)

    # send out email message.
    send_mail(email_subject,
              email_msg,
              DEFAULT_FROM_EMAIL,
              (user.email, ))


def _check_set_role(request, organization, username, required=False):
    """
    Confirms the role and assigns the role to the organization
    """

    role = request.DATA.get('role')
    role_cls = ROLES.get(role)

    if not role or not role_cls:
        if required:
            message = (_(u"'%s' is not a valid role." % role) if role
                       else _(u"This field is required."))
        else:
            message = _(u"'%s' is not a valid role." % role)

        return status.HTTP_400_BAD_REQUEST, {'role': [message]}
    else:
        _update_username_role(organization, username, role_cls)

        # add the owner to owners team
        if role == OwnerRole.name:
            add_user_to_team(get_organization_owners_team(organization),
                             User.objects.get(username=username))

        return (status.HTTP_200_OK, []) if request.method == 'PUT' \
            else (status.HTTP_201_CREATED, [])


class OrganizationProfileViewSet(LastModifiedMixin,
                                 ObjectLookupMixin,
                                 ModelViewSet):

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

## Partial updates of Organization Profile Information

Organization profile properties can be updated using `PATCH` http method.
Payload required is for properties that are to be changed in JSON, for example
, `{"metadata": {"computer": "mac"}}` will set the metadata to
`{"computer": "mac"}`.

<pre class="prettyprint"><b>PATCH</b> /api/v1/orgs/{username}</pre>
> Example
>
>     \
curl -X PATCH -d '{"metadata": {"computer": "mac"}}' https://ona.io/api/v1/\
profiles/modilabs -H "Content-Type: application/json"

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
>            "metadata": {
>                "computer": "mac"
>             },
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
`{"username": "member1"}`. You can add an optional parameter to define the role
of the user.`{"username": "member1", "role": "editor"}`

<pre class="prettyprint"><b>POST</b> /api/v1/orgs/{username}/members</pre>
> Example
>
>       curl -X POST -d '{"username": "member1"}' \
https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

> Response
>
>       ["member1"]

## Send an email to a user added to an organization
An email is only sent when the `email_msg` request variable is present,
`email_subject` is optional.
<pre class="prettyprint">
<b>POST</b> /api/v1/orgs/{username}/members
</pre>

> Example
>
>       curl -X POST -d '{"username": "member1",\
"email_msg": "You have been added to modilabs",\
"email_subject": "Your have been added "}'\
  https://ona.io/api/v1/orgs/modilabs/members \
  -H "Content-Type: application/json"

> Response
>
>        ["member1"]

## Change the role of a user in an organization

To change the role of a user in an organization pass the username and role
`{"username": "member1", "role": "owner|manager|editor|dataentry|readonly"}`.

<pre class="prettyprint"><b>PUT</b> /api/v1/orgs/{username}/members</pre>
> Example
>
>       curl -X PUT -d '{"username": "member1", "role": "editor"}' \
https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

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
https://ona.io/api/v1/orgs/modilabs/members -H "Content-Type: application/json"

> Response
>
>       []
"""
    queryset = OrganizationProfile.objects.all()
    serializer_class = OrganizationSerializer
    lookup_field = 'user'
    permission_classes = [permissions.DjangoObjectPermissionsAllowAnon]
    filter_backends = (OrganizationPermissionFilter,)

    @action(methods=['DELETE', 'GET', 'POST', 'PUT'])
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        status_code = status.HTTP_200_OK
        data = []
        username = request.DATA.get('username') or request.QUERY_PARAMS.get(
            'username')

        if request.method in ['DELETE', 'POST', 'PUT'] and not username:
            status_code = status.HTTP_400_BAD_REQUEST
            data = {'username': [_(u"This field is required.")]}
        elif request.method == 'POST':
            data, status_code = _add_username_to_organization(
                organization, username)

            if ('email_msg' in request.DATA or
                    'email_msg' in request.QUERY_PARAMS) \
                    and status_code == 201:
                _compose_send_email(request, organization, username)

            if 'role' in request.DATA:
                status_code, data = _check_set_role(request,
                                                    organization,
                                                    username)

        elif request.method == 'PUT':
            status_code, data = _check_set_role(request, organization,
                                                username, required=True)

        elif request.method == 'DELETE':
            data, status_code = _remove_username_to_organization(
                organization, username)

        if status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            members = get_organization_members(organization)
            data = [u.username for u in members]

        return Response(data, status=status_code)
