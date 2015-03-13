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
                                    add_user_to_team,
                                    remove_user_from_team)
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


def _add_role(org, user, role_cls):
    return role_cls.add(user, org)


def _update_username_role(organization, username, role_cls):
    def _set_organization_role_to_user(org, user, role_cls):
        role_cls.add(user, organization)

    return _try_function_org_username(_set_organization_role_to_user,
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

        owners_team = get_organization_owners_team(organization)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            data = {'username': [_(u"User `%(username)s` does not exist."
                                   % {'username': username})]}

            return (status.HTTP_400_BAD_REQUEST, data)

        # add the owner to owners team
        if role == OwnerRole.name:
            add_user_to_team(owners_team, user)

        if role != OwnerRole.name:
            remove_user_from_team(owners_team, user)

        return (status.HTTP_200_OK, []) if request.method == 'PUT' \
            else (status.HTTP_201_CREATED, [])


class OrganizationProfileViewSet(LastModifiedMixin,
                                 ObjectLookupMixin,
                                 ModelViewSet):
    """
    List, Retrieve, Update, Create/Register Organizations.
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
