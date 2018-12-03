# -*- coding=utf-8 -*-
"""
API util functions.
"""
import importlib
import os
import tempfile
from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.storage import get_storage_class
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator, ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from future.utils import listitems
from guardian.shortcuts import assign_perm, get_perms_for_model, remove_perm
from guardian.shortcuts import get_perms
from kombu.exceptions import OperationalError
from registration.models import RegistrationProfile
from rest_framework import exceptions
from taggit.forms import TagField

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from onadata.apps.logger.models import DataView, Instance, Project, XForm
from onadata.apps.main.forms import QuickConverter
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.models.parsed_instance import datetime_from_str
from onadata.libs.baseviewset import DefaultBaseViewset
from onadata.libs.models.share_project import ShareProject
from onadata.libs.permissions import (
    ROLES, DataEntryMinorRole, DataEntryOnlyRole, DataEntryRole,
    EditorMinorRole, EditorRole, ManagerRole, OwnerRole, get_role,
    get_role_in_org, is_organization)
from onadata.libs.utils.api_export_tools import custom_response_handler
from onadata.libs.utils.cache_tools import (PROJ_BASE_FORMS_CACHE,
                                            PROJ_FORMS_CACHE, safe_delete)
from onadata.libs.utils.common_tags import MEMBERS, XFORM_META_PERMS
from onadata.libs.utils.logger_tools import (publish_form,
                                             response_with_mimetype_and_name)
from onadata.libs.utils.project_utils import (set_project_perms_to_xform,
                                              set_project_perms_to_xform_async)
from onadata.libs.utils.user_auth import (check_and_set_form_by_id,
                                          check_and_set_form_by_id_string)

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
    """
    Returns XForm queryset of the forms based on the arguments owner,
    shared_form and shared_data.

    Returns only public forms if owner is 'public' otherwise returns forms
    belonging to owner.
    """
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
    organization, _created = User.objects.get_or_create(username__iexact=name)
    organization_profile = OrganizationProfile.objects.create(
        user=organization, creator=creator)
    return organization_profile


def create_organization_object(org_name, creator, attrs=None):
    '''Creates an OrganizationProfile object without saving to the database'''
    attrs = attrs if attrs else {}
    name = attrs.get('name', org_name) if attrs else org_name
    first_name, last_name = _get_first_last_names(name)
    email = attrs.get('email', u'') if attrs else u''
    new_user = User(
        username=org_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_active=True)
    new_user.save()
    registration_profile = RegistrationProfile.objects.create_profile(new_user)
    if email:
        site = Site.objects.get(pk=settings.SITE_ID)
        registration_profile.send_activation_email(site)
    profile = OrganizationProfile(
        user=new_user,
        name=name,
        creator=creator,
        created_by=creator,
        city=attrs.get('city', u''),
        country=attrs.get('country', u''),
        organization=attrs.get('organization', u''),
        home_page=attrs.get('home_page', u''),
        twitter=attrs.get('twitter', u''))
    return profile


def create_organization_team(organization, name, permission_names=None):
    """
    Creates an organization team with the given permissions as defined in
    permission_names.
    """
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
        team = Team.objects.get(name=u'%s#%s' % (organization.user.username,
                                                 MEMBERS))
    except Team.DoesNotExist:
        team = create_organization_team(organization, MEMBERS)
        add_user_to_team(team, organization.user)

    return team


def get_organization_owners_team(org):
    """
    Get the owners team of an organization
    :param org: organization
    :return: Owners team of the organization
    """
    return Team.objects.get(
        name="{}#{}".format(org.user.username, Team.OWNER_TEAM_NAME),
        organization=org.user)


def remove_user_from_organization(organization, user):
    """Remove a user from an organization"""
    team = get_organization_members_team(organization)
    remove_user_from_team(team, user)
    owners_team = get_organization_owners_team(organization)
    remove_user_from_team(owners_team, user)

    role = get_role_in_org(user, organization)
    # Remove user from all org projects
    for project in organization.user.project_org.all():
        ShareProject(project, user.username, role, remove=True).save()


def remove_user_from_team(team, user):
    """
    Removes given user from the team and also removes team permissions from the
    user.
    """
    user.groups.remove(team)

    # remove the permission
    remove_perm('view_team', user, team)

    # if team is owners team remove more perms
    if team.name.find(Team.OWNER_TEAM_NAME) > 0:
        owners_team = get_organization_owners_team(team.organization.profile)
        members_team = get_organization_members_team(team.organization.profile)
        for perm in get_perms_for_model(Team):
            remove_perm(perm.codename, user, owners_team)
            remove_perm(perm.codename, user, members_team)


def add_user_to_organization(organization, user):
    """Add a user to an organization"""

    team = get_organization_members_team(organization)
    add_user_to_team(team, user)


def add_user_to_team(team, user):
    """
    Adds a user to a team and assigns them team permissions.
    """
    user.groups.add(team)

    # give the user perms to view the team
    assign_perm('view_team', user, team)

    # if team is owners team assign more perms
    if team.name.find(Team.OWNER_TEAM_NAME) > 0:
        _assign_organization_team_perms(team.organization, user)


def _assign_organization_team_perms(organization, user):
    owners_team = get_organization_owners_team(organization.profile)
    members_team = get_organization_members_team(organization.profile)
    for perm in get_perms_for_model(Team):
        assign_perm(perm.codename, user, owners_team)
        assign_perm(perm.codename, user, members_team)


def get_organization_members(organization):
    """Get members team user queryset"""
    team = get_organization_members_team(organization)

    return team.user_set.all()


def _get_owners(organization):
    # Get users with owners perms and not the org itself

    return [
        user
        for user in get_organization_owners_team(organization).user_set.all()
        if get_role_in_org(user, organization) == 'owner'
        and organization.user != user
    ]


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

    project = Project.objects.create(
        name=project_name,
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
    """
    Publishes XLSForm given a request.
    """
    return do_publish_xlsform(request.user, request.data, request.FILES, owner,
                              id_string, project)


# pylint: disable=too-many-arguments
def do_publish_xlsform(user, post, files, owner, id_string=None, project=None):
    """
    Publishes XLSForm.
    """
    if id_string and project:
        xform = get_object_or_404(
            XForm, user=owner, id_string=id_string, project=project)
        if not ManagerRole.user_has_role(user, xform):
            raise exceptions.PermissionDenied(
                _("{} has no manager/owner role to the form {}".format(
                    user, xform)))
    elif not user.has_perm('can_add_xform', owner.profile):
        raise exceptions.PermissionDenied(
            detail=_(u"User %(user)s has no permission to add xforms to "
                     "account %(account)s" % {
                         'user': user.username,
                         'account': owner.username
                     }))

    def set_form():
        """
        Instantiates QuickConverter form to publish a form.
        """

        if project:
            args = (post and dict(listitems(post))) or {}
            args['project'] = project.pk
        else:
            args = post

        form = QuickConverter(args, files)

        return form.publish(owner, id_string=id_string, created_by=user)

    return publish_form(set_form)


def publish_project_xform(request, project):
    """
    Publish XLSForm to a project given a request.
    """

    def set_form():
        """
        Instantiates QuickConverter form to publish a form.
        """
        props = {
            'project': project.pk,
            'dropbox_xls_url': request.data.get('dropbox_xls_url'),
            'xls_url': request.data.get('xls_url'),
            'csv_url': request.data.get('csv_url'),
            'text_xls_form': request.data.get('text_xls_form')
        }

        form = QuickConverter(props, request.FILES)

        return form.publish(project.organization, created_by=request.user)

    xform = None

    def id_string_exists_in_account():
        """
        Checks if an id_string exists in an account, returns True if it exists
        otherwise returns False.
        """
        try:
            XForm.objects.get(
                user=project.organization, id_string=xform.id_string)
        except XForm.DoesNotExist:
            return False
        return True

    if 'formid' in request.data:
        xform = get_object_or_404(XForm, pk=request.data.get('formid'))
        safe_delete('{}{}'.format(PROJ_FORMS_CACHE, xform.project.pk))
        safe_delete('{}{}'.format(PROJ_BASE_FORMS_CACHE, xform.project.pk))
        if not ManagerRole.user_has_role(request.user, xform):
            raise exceptions.PermissionDenied(
                _("{} has no manager/owner role to the form {}".format(
                    request.user, xform)))

        msg = 'Form with the same id_string already exists in this account'
        # Without this check, a user can't transfer a form to projects that
        # he/she owns because `id_string_exists_in_account` will always
        # return true
        if project.organization != xform.user and \
                id_string_exists_in_account():
            raise exceptions.ParseError(_(msg))
        xform.user = project.organization
        xform.project = project

        try:
            with transaction.atomic():
                xform.save()
        except IntegrityError:
            raise exceptions.ParseError(_(msg))
        else:
            # First assign permissions to the person who uploaded the form
            OwnerRole.add(request.user, xform)
            try:
                # Next run async task to apply all other perms
                set_project_perms_to_xform_async.delay(xform.pk, project.pk)
            except OperationalError:
                # Apply permissions synchrounously
                set_project_perms_to_xform(xform, project)
    else:
        xform = publish_form(set_form)

    return xform


def get_xform(formid, request, username=None):
    """
    Returns XForm instance if request.user has permissions to it otherwise it
    raises PermissionDenied() exception.
    """
    try:
        formid = int(formid)
    except ValueError:
        username = username is None and request.user.username
        xform = check_and_set_form_by_id_string(username, formid, request)
    else:
        xform = check_and_set_form_by_id(int(formid), request)

    if not xform:
        raise exceptions.PermissionDenied(
            _("You do not have permission to view data from this form."))

    return xform


def get_user_profile_or_none(username):
    """
    Returns a UserProfile instance if the user exists otherwise returns None.
    """
    profile = None

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        pass
    else:
        profile = user.profile

    return profile


def get_instance_xform_or_none(instance_id):
    """
    Returns the XForm an Instance belongs to
    """
    xform = None

    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        pass
    else:
        xform = instance.xform

    return xform


def add_tags_to_instance(request, instance):
    """
    Add tags to an instance.
    """

    class TagForm(forms.Form):
        """
        Simple TagForm class to validate tags in a request.
        """
        tags = TagField()

    form = TagForm(request.data)

    if form.is_valid():
        tags = form.cleaned_data.get('tags', None)

        if tags:
            for tag in tags:
                instance.tags.add(tag)
    else:
        raise exceptions.ParseError(form.errors)


def get_media_file_response(metadata, request=None):
    """
    Returns a HTTP response for media files.

    HttpResponse 200 if it represents a file on disk.
    HttpResponseRedirect 302 incase the metadata represents a url.
    HttpResponseNotFound 404 if the metadata file cannot be found.
    """

    def get_data_value_objects(value):
        """
        Returns a tuple of a DataView or XForm and the name of the media file.

        Looks for 'dataview 123 fruits.csv' or 'xform 345 fruits.csv'.
        """
        model = None
        if value.startswith('dataview'):
            model = DataView
        elif value.startswith('xform'):
            model = XForm

        if model:
            parts = value.split()
            if len(parts) > 1:
                name = parts[2] if len(parts) > 2 else None

                return (get_object_or_404(model, pk=parts[1]), name)

        return (None, None)

    if metadata.data_file:
        file_path = metadata.data_file.name
        filename, extension = os.path.splitext(file_path.split('/')[-1])
        extension = extension.strip('.')
        dfs = get_storage_class()()

        if dfs.exists(file_path):
            response = response_with_mimetype_and_name(
                metadata.data_file_type,
                filename,
                extension=extension,
                show_date=False,
                file_path=file_path,
                full_mime=True)

            return response
        return HttpResponseNotFound()
    try:
        URLValidator()(metadata.data_value)
    except ValidationError:
        obj, filename = get_data_value_objects(metadata.data_value)
        if obj:
            dataview = obj if isinstance(obj, DataView) else False
            xform = obj.xform if isinstance(obj, DataView) else obj

            return custom_response_handler(
                request,
                xform, {},
                Export.CSV_EXPORT,
                filename=filename,
                dataview=dataview)

    return HttpResponseRedirect(metadata.data_value)


# pylint: disable=invalid-name
def check_inherit_permission_from_project(xform_id, user):
    """
    Checks if a user has the same project permissions for the given xform_id,
    if there is a difference applies the project permissions to the user for
    the given xform_id.
    """
    if xform_id == 'public':
        return

    try:
        int(xform_id)
    except ValueError:
        return

    # get the project_xform
    xform = XForm.objects.filter(pk=xform_id).select_related('project').only(
        'project_id', 'id').first()

    if not xform:
        return

    # ignore if forms has meta perms set
    if xform.metadata_set.filter(data_type=XFORM_META_PERMS):
        return

    # get and compare the project role to the xform role
    project_role = get_role_in_org(user, xform.project)
    xform_role = get_role_in_org(user, xform)

    # if diff set the project role to the xform
    if xform_role != project_role:
        _set_xform_permission(project_role, user, xform)


def _set_xform_permission(role, user, xform):
    role_class = ROLES.get(role)

    if role_class:
        role_class.add(user, xform)


def load_class(full_class_string):
    """
    dynamically load a class from a string
    """

    class_data = full_class_string.split(".")
    module_path = ".".join(class_data[:-1])
    class_str = class_data[-1]

    module = importlib.import_module(module_path)
    # Finally, we retrieve the Class
    return getattr(module, class_str)


def get_baseviewset_class():
    """
    Checks the setting if the default viewset is implementded otherwise loads
    the default in onadata
    :return: the default baseviewset
    """
    return load_class(settings.BASE_VIEWSET) \
        if settings.BASE_VIEWSET else DefaultBaseViewset


def generate_tmp_path(uploaded_csv_file):
    """
    Write file to temporary folder if not already there
    :param uploaded_csv_file:
    :return: path to the tmp folder
    """
    if isinstance(uploaded_csv_file, InMemoryUploadedFile):
        uploaded_csv_file.open()
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(uploaded_csv_file.read())
        tmp_path = tmp_file.name
        uploaded_csv_file.close()
    else:
        tmp_path = uploaded_csv_file.temporary_file_path()

    return tmp_path


def get_xform_users(xform):
    """
    Utility function that returns users and their roles in a form.
    :param xform:
    :return:
    """
    data = {}
    org_members = []
    for perm in xform.xformuserobjectpermission_set.all():
        if perm.user not in data:
            user = perm.user

            if is_organization(user.profile):
                org_members = get_team_members(user.username)

            data[user] = {
                'permissions': [],
                'is_org': is_organization(user.profile),
                'metadata': user.profile.metadata,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user': user.username
            }
        if perm.user in data:
            data[perm.user]['permissions'].append(perm.permission.codename)

    for user in org_members:
        if user not in data:
            data[user] = {
                'permissions': get_perms(user, xform),
                'is_org': is_organization(user.profile),
                'metadata': user.profile.metadata,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user': user.username
            }

    for k in data:
        data[k]['permissions'].sort()
        data[k]['role'] = get_role(data[k]['permissions'], xform)
        del data[k]['permissions']

    return data


def get_team_members(org_username):
    """Return members team if it exists else none.

    :param org_username: organization name
    :return: team
    """
    members = []
    try:
        team = Team.objects.get(
            name="{}#{}".format(org_username, MEMBERS))
    except Team.DoesNotExist:
        pass
    else:
        members = team.user_set.all()

    return members


def update_role_by_meta_xform_perms(xform):
    """
    Updates users role in a xform based on meta permissions set on the form.
    """
    # load meta xform perms
    metadata = MetaData.xform_meta_permission(xform)
    editor_role_list = [EditorRole, EditorMinorRole]
    editor_role = {role.name: role for role in editor_role_list}

    dataentry_role_list = [
        DataEntryMinorRole, DataEntryOnlyRole, DataEntryRole
    ]
    dataentry_role = {role.name: role for role in dataentry_role_list}

    if metadata:
        meta_perms = metadata.data_value.split('|')

        # update roles
        users = get_xform_users(xform)

        for user in users:

            role = users.get(user).get('role')
            if role in editor_role:
                role = ROLES.get(meta_perms[0])
                role.add(user, xform)

            if role in dataentry_role:
                role = ROLES.get(meta_perms[1])
                role.add(user, xform)
