import os

from datetime import datetime

from guardian.shortcuts import assign_perm, remove_perm
from django import forms
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Q
from django.http import HttpResponseNotFound
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from taggit.forms import TagField
from rest_framework import exceptions
from registration.models import RegistrationProfile
from django.core.validators import ValidationError

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from onadata.apps.main.forms import QuickConverter
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.parsed_instance import datetime_from_str
from onadata.libs.utils.logger_tools import publish_form
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.project_utils import set_project_perms_to_xform
from onadata.libs.utils.user_auth import check_and_set_form_by_id
from onadata.libs.utils.user_auth import check_and_set_form_by_id_string
from onadata.libs.permissions import ROLES
from onadata.libs.permissions import ManagerRole
from onadata.libs.permissions import get_role_in_org

DECIMAL_PRECISION = 2


def _get_first_last_names(name):
    name_split = name.split()
    first_name = name_split[0]
    last_name = u''
    if len(name_split) > 1:
        last_name = u' '.join(name_split[1:])
    return first_name, last_name


def _get_id_for_type(record, mongo_field):
    date_field = datetime_from_str(record[mongo_field])
    mongo_str = '$' + mongo_field

    return {"$substr": [mongo_str, 0, 10]} if isinstance(date_field, datetime)\
        else mongo_str


def get_accessible_forms(owner=None, shared_form=False, shared_data=False):
    xforms = XForm.objects.filter()

    if shared_form and not shared_data:
        xforms = xforms.filter(shared=True)
    elif (shared_form and shared_data) or \
            (owner == 'public' and not shared_form and not shared_data):
        xforms = xforms.filter(Q(shared=True) | Q(shared_data=True))
    elif not shared_form and shared_data:
        xforms = xforms.filter(shared_data=True)

    if owner != 'public':
        xforms = xforms.filter(user__username=owner)

    return xforms.distinct()


def create_organization(name, creator):
    """
    Organization created by a user
    - create a team, OwnerTeam with full permissions to the creator
    - Team(name='Owners', organization=organization).save()

    """
    organization, created = User.objects.get_or_create(username__iexact=name)
    organization_profile = OrganizationProfile.objects.create(
        user=organization, creator=creator)
    return organization_profile


def create_organization_object(org_name, creator, attrs={}):
    '''Creates an OrganizationProfile object without saving to the database'''
    name = attrs.get('name', org_name)
    first_name, last_name = _get_first_last_names(name)
    email = attrs.get('email', u'')
    new_user = User(username=org_name, first_name=first_name,
                    last_name=last_name, email=email, is_active=True)
    new_user.save()
    registration_profile = RegistrationProfile.objects.create_profile(new_user)
    if email:
        site = Site.objects.get(pk=settings.SITE_ID)
        registration_profile.send_activation_email(site)
    profile = OrganizationProfile(
        user=new_user, name=name, creator=creator,
        created_by=creator,
        city=attrs.get('city', u''),
        country=attrs.get('country', u''),
        organization=attrs.get('organization', u''),
        home_page=attrs.get('home_page', u''),
        twitter=attrs.get('twitter', u''))
    return profile


def create_organization_team(organization, name, permission_names=[]):
    organization = organization.user \
        if isinstance(organization, OrganizationProfile) else organization
    team = Team.objects.create(organization=organization, name=name)
    content_type = ContentType.objects.get(
        app_label='api', model='organizationprofile')
    if permission_names:
        # get permission objects
        perms = Permission.objects.filter(
            codename__in=permission_names, content_type=content_type)
        if perms:
            team.permissions.add(*tuple(perms))
    return team


def get_organization_members_team(organization):
    """Get organization members team
    create members team if it does not exist and add organization owner
    to the members team"""
    try:
        team = Team.objects.get(
            name=u'%s#%s' % (organization.user.username, 'members'))
    except Team.DoesNotExist:
        team = create_organization_team(organization, 'members')
        add_user_to_team(team, organization.user)

    return team


def get_organization_owners_team(org):
    """
    Get the owners team of an organization
    :param org: organization
    :return: Owners team of the organization
    """
    return Team.objects.get(name="{}#{}".format(org.user.username,
                                                Team.OWNER_TEAM_NAME),
                            organization=org.user)


def remove_user_from_organization(organization, user):
    """Remove a user from an organization"""
    owners = _get_owners(organization)
    if user in owners and len(owners) <= 1:
        raise ValidationError(_("Organization cannot be without an owner"))
    team = get_organization_members_team(organization)
    remove_user_from_team(team, user)


def remove_user_from_team(team, user):
    user.groups.remove(team)

    # remove the permission
    remove_perm('view_team', user, team)


def add_user_to_organization(organization, user):
    """Add a user to an organization"""
    team = get_organization_members_team(organization)
    add_user_to_team(team, user)


def add_user_to_team(team, user):
    user.groups.add(team)

    # give the user perms to view the team
    assign_perm('view_team', user, team)


def get_organization_members(organization):
    """Get members team user queryset"""
    team = get_organization_members_team(organization)

    return team.user_set.all()


def _get_owners(organization):
    # Get users with owners perms and not the org itself
    return [user for user in get_organization_members(organization)
            if get_role_in_org(user, organization) == 'owner' and
            organization.user != user]


def create_organization_project(organization, project_name, created_by):
    """Creates a project for a given organization
    :param organization: User organization
    :param project_name
    :param created_by: User with permissions to create projects within the
                       organization

    :returns: a Project instance
    """
    profile = OrganizationProfile.objects.get(user=organization)

    if not profile.is_organization_owner(created_by):
        return None

    project = Project.objects.create(name=project_name,
                                     organization=organization,
                                     created_by=created_by,
                                     metadata='{}')

    return project


def add_team_to_project(team, project):
    """Adds a  team to a project

    :param team:
    :param project:

    :returns: True if successful or project has already been added to the team
    """
    if isinstance(team, Team) and isinstance(project, Project):
        if not team.projects.filter(pk=project.pk):
            team.projects.add(project)
        return True
    return False


def publish_xlsform(request, owner, id_string=None, project=None):
    return do_publish_xlsform(
        request.user, request.DATA, request.FILES, owner, id_string,
        project)


def do_publish_xlsform(user, post, files, owner, id_string=None, project=None):
    if id_string and project:
        xform = get_object_or_404(XForm, user=owner, id_string=id_string,
                                  project=project)
        if not ManagerRole.user_has_role(user, xform):
            raise exceptions.PermissionDenied(_(
                "{} has no manager/owner role to the form {}". format(
                    user, xform)))
    elif not user.has_perm('can_add_xform', owner.profile):
        raise exceptions.PermissionDenied(
            detail=_(u"User %(user)s has no permission to add xforms to "
                     "account %(account)s" % {'user': user.username,
                                              'account': owner.username}))

    def set_form():

        if project:
            args = dict({'project': project.pk}.items() + post.items())
        else:
            args = post

        form = QuickConverter(args,  files)

        return form.publish(owner, id_string=id_string, created_by=user)

    return publish_form(set_form)


def publish_project_xform(request, project):
    def set_form():
        props = {
            'project': project.pk,
            'dropbox_xls_url': request.DATA.get('dropbox_xls_url'),
            'xls_url': request.DATA.get('xls_url'),
            'csv_url': request.DATA.get('csv_url'),
            'text_xls_form': request.DATA.get('text_xls_form')
        }

        form = QuickConverter(props, request.FILES)

        return form.publish(project.organization, created_by=request.user)

    xform = None

    if 'formid' in request.DATA:
        xform = get_object_or_404(XForm, pk=request.DATA.get('formid'))
        if not ManagerRole.user_has_role(request.user, xform):
            raise exceptions.PermissionDenied(_(
                "{} has no manager/owner role to the form {}". format(
                    request.user, xform)))
        xform.project = project
        xform.save()
        set_project_perms_to_xform(xform, project)
    else:
        xform = publish_form(set_form)

    return xform


def get_xform(formid, request, username=None):
    try:
        formid = int(formid)
    except ValueError:
        username = username is None and request.user.username
        xform = check_and_set_form_by_id_string(username, formid, request)
    else:
        xform = check_and_set_form_by_id(int(formid), request)

    if not xform:
        raise exceptions.PermissionDenied(_(
            "You do not have permission to view data from this form."))

    return xform


def get_user_profile_or_none(username):
    profile = None

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        pass
    else:
        profile = user.profile

    return profile


def add_tags_to_instance(request, instance):
    class TagForm(forms.Form):
        tags = TagField()

    form = TagForm(request.DATA)

    if form.is_valid():
        tags = form.cleaned_data.get('tags', None)

        if tags:
            for tag in tags:
                instance.tags.add(tag)
    else:
        raise exceptions.ParseError(form.errors)


def get_media_file_response(metadata):
    if metadata.data_file:
        file_path = metadata.data_file.name
        filename, extension = os.path.splitext(file_path.split('/')[-1])
        extension = extension.strip('.')
        dfs = get_storage_class()()

        if dfs.exists(file_path):
            response = response_with_mimetype_and_name(
                metadata.data_file_type,
                filename, extension=extension, show_date=False,
                file_path=file_path, full_mime=True)

            return response
        else:
            return HttpResponseNotFound()
    else:
        return HttpResponseRedirect(metadata.data_value)


def check_inherit_permission_from_project(xform_id, user):
    if xform_id == 'public':
        return

    try:
        int(xform_id)
    except ValueError:
        return

    # get the project_xform
    xforms = XForm.objects.filter(pk=xform_id)

    if not xforms:
        return

    # get and compare the project role to the xform role
    project_role = get_role_in_org(user, xforms[0].project)
    xform_role = get_role_in_org(user, xforms[0])

    # if diff set the project role to the xform
    if xform_role != project_role:
        _set_xform_permission(project_role, user, xforms[0])


def _set_xform_permission(role, user, xform):
    role_class = ROLES.get(role)

    if role_class:
        role_class.add(user, xform)
