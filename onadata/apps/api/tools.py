# -*- coding: utf-8 -*-
"""
API utility functions.
"""

import importlib
import os
import tempfile
from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.files.storage import storages
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator, ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from guardian.shortcuts import get_perms, get_perms_for_model, remove_perm
from kombu.exceptions import OperationalError
from multidb.pinning import use_master
from registration.models import RegistrationProfile
from rest_framework import exceptions
from six import iteritems
from taggit.forms import TagField

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile, add_user_to_team,
    get_or_create_organization_owners_team, get_organization_members_team)
from onadata.apps.api.models.team import Team
from onadata.apps.logger.models import (DataView, EntityList, Instance,
                                        Project, XForm)
from onadata.apps.main.forms import QuickConverter
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.viewer.models.parsed_instance import datetime_from_str
from onadata.libs.baseviewset import DefaultBaseViewset
from onadata.libs.permissions import (ROLES, ROLES_ORDERED, DataEntryMinorRole,
                                      DataEntryOnlyRole, DataEntryRole,
                                      EditorMinorRole, EditorRole, ManagerRole,
                                      OwnerRole, get_role, get_role_in_org,
                                      get_team_project_default_permissions,
                                      is_organization)
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.libs.utils.api_export_tools import (
    custom_response_handler, get_entity_list_export_response,
    get_metadata_format)
from onadata.libs.utils.cache_tools import (ORG_PROFILE_CACHE,
                                            PROJ_BASE_FORMS_CACHE,
                                            PROJ_FORMS_CACHE,
                                            PROJ_NUM_DATASET_CACHE,
                                            PROJ_OWNER_CACHE,
                                            PROJ_SUB_DATE_CACHE,
                                            XFORM_LIST_CACHE,
                                            reset_project_cache, safe_delete)
from onadata.libs.utils.common_tags import MEMBERS, XFORM_META_PERMS
from onadata.libs.utils.logger_tools import (publish_form,
                                             response_with_mimetype_and_name)
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.project_utils import (set_project_perms_to_xform,
                                              set_project_perms_to_xform_async)
from onadata.libs.utils.user_auth import (check_and_set_form_by_id,
                                          check_and_set_form_by_id_string)

DECIMAL_PRECISION = 2

# pylint: disable=invalid-name
User = get_user_model()


def _get_first_last_names(name):
    name_split = name.split()
    first_name = name_split[0]
    last_name = ""
    if len(name_split) > 1:
        last_name = " ".join(name_split[1:])
    return first_name, last_name


def _get_id_for_type(record, mongo_field):
    date_field = datetime_from_str(record[mongo_field])
    mongo_str = "$" + mongo_field

    return (
        {"$substr": [mongo_str, 0, 10]}
        if isinstance(date_field, datetime)
        else mongo_str
    )


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
    elif (shared_form and shared_data) or (
        owner == "public" and not shared_form and not shared_data
    ):
        xforms = xforms.filter(Q(shared=True) | Q(shared_data=True))
    elif not shared_form and shared_data:
        xforms = xforms.filter(shared_data=True)

    if owner != "public":
        xforms = xforms.filter(user__username=owner)

    return xforms.distinct()


def create_organization(name, creator):
    """
    Organization created by a user
    - create a team, OwnerTeam with full permissions to the creator
    - Team(name='Owners', organization=organization).save()

    """
    organization, _created = User.objects.get_or_create(username__iexact=name)
    organization_profile, _ = OrganizationProfile.objects.get_or_create(
        user=organization, creator=creator
    )
    return organization_profile


def create_organization_object(org_name, creator, attrs=None):
    """Creates an OrganizationProfile object without saving to the database"""
    attrs = attrs if attrs else {}
    name = attrs.get("name", org_name) if attrs else org_name
    first_name, last_name = _get_first_last_names(name)
    email = attrs.get("email", "") if attrs else ""
    new_user = User(
        username=org_name,
        first_name=first_name,
        last_name=last_name,
        is_active=getattr(settings, "ORG_ON_CREATE_IS_ACTIVE", True),
    )
    new_user.save()
    try:
        RegistrationProfile.objects.create_profile(new_user)
    except IntegrityError as e:
        raise ValidationError(_(f"{org_name} already exists")) from e
    profile = OrganizationProfile(
        user=new_user,
        name=name,
        creator=creator,
        created_by=creator,
        city=attrs.get("city", ""),
        country=attrs.get("country", ""),
        organization=attrs.get("organization", ""),
        home_page=attrs.get("home_page", ""),
        twitter=attrs.get("twitter", ""),
        email=email,
    )
    return profile


def remove_user_from_organization(organization, user):
    """Remove a user from an organization

    Remove user from organization and all projects in the organization

    :param organization: OrganizationProfile instance
    :param user: User instance
    :return: None
    """
    team = get_organization_members_team(organization)
    remove_user_from_team(team, user)
    owners_team = get_or_create_organization_owners_team(organization)
    remove_user_from_team(owners_team, user)

    role = get_role_in_org(user, organization)
    role_cls = ROLES.get(role)

    if role_cls:
        # Remove object permissions
        role_cls.remove_obj_permissions(user, organization)
        role_cls.remove_obj_permissions(user, organization.userprofile_ptr)

    # Invalidate organization cache
    invalidate_organization_cache(organization.user.username)

    # Avoid cyclic dependency errors
    api_tasks = importlib.import_module("onadata.apps.api.tasks")

    # Remove user from all org projects
    project_qs = organization.user.project_org.all()

    for project in queryset_iterator(project_qs):
        api_tasks.share_project_async.delay(
            project.pk, user.username, role, remove=True
        )


def remove_user_from_team(team, user):
    """
    Removes given user from the team and also removes team permissions from the
    user.
    """
    user.groups.remove(team)

    # remove the permission
    remove_perm("view_team", user, team)

    # if team is owners team remove more perms
    if team.name.find(Team.OWNER_TEAM_NAME) > 0:
        owners_team = get_or_create_organization_owners_team(team.organization.profile)
        members_team = get_organization_members_team(team.organization.profile)
        for perm in get_perms_for_model(Team):
            remove_perm(perm.codename, user, owners_team)
            remove_perm(perm.codename, user, members_team)


def add_user_to_organization(organization, user, role=None):
    """Add a user to an organization

    Add user to organization and all projects in the organization

    :param organization: OrganizationProfile instance
    :param user: User instance
    :param role: Role name
    :return: None
    """

    team = get_organization_members_team(organization)
    add_user_to_team(team, user)

    if role is not None:
        role_cls = ROLES.get(role)
        role_cls.add(user, organization)

        owners_team = get_or_create_organization_owners_team(organization)

        if role == OwnerRole.name:
            role_cls.add(user, organization.userprofile_ptr)
            # Add user to their respective team
            add_user_to_team(owners_team, user)

        else:
            remove_user_from_team(owners_team, user)
            OwnerRole.remove_obj_permissions(user, organization.userprofile_ptr)

    # Invalidate organization cache
    invalidate_organization_cache(organization.user.username)

    # Avoid cyclic dependency errors
    api_tasks = importlib.import_module("onadata.apps.api.tasks")

    # Share all organization projects with the new user
    project_qs = organization.user.project_org.all()

    if role == OwnerRole.name:
        # New owners have owner role on all projects
        for project in queryset_iterator(project_qs):
            api_tasks.share_project_async.delay(project.pk, user.username, role)

    else:
        # New members & managers gain default team permissions on projects
        team = get_organization_members_team(organization)

        for project in queryset_iterator(project_qs):
            if role == ManagerRole.name and project.created_by == user:
                # New managers are only granted the manager role on the
                # projects they created
                api_tasks.share_project_async.delay(project.pk, user.username, role)
            else:
                project_role = get_team_project_default_permissions(team, project)
                api_tasks.share_project_async.delay(
                    project.pk, user.username, project_role
                )


def get_organization_members(organization):
    """Get members team user queryset"""
    team = get_organization_members_team(organization)

    return team.user_set.filter(is_active=True)


def get_organization_owners(organization):
    """Get owners team user queryset"""
    team = get_or_create_organization_owners_team(organization)
    return team.user_set.filter(is_active=True)


def _get_owners(organization):
    # Get users with owners perms and not the org itself

    return [
        user
        for user in get_or_create_organization_owners_team(organization).user_set.all()
        if get_role_in_org(user, organization) == "owner" and organization.user != user
    ]


def create_organization_project(organization, project_name, created_by):
    """Creates a project for a given organization
    :param organization: User organization
    :param project_name
    :param created_by: User with permissions to create projects within the organization

    :returns: a Project instance
    """
    profile = OrganizationProfile.objects.get(user=organization)

    if not profile.is_organization_owner(created_by):
        return None

    project = Project.objects.create(
        name=project_name,
        organization=organization,
        created_by=created_by,
        metadata="{}",
    )

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
    Publishes XLSForm & creates an XFormVersion object given a request.
    """
    survey = do_publish_xlsform(
        request.user, request.data, request.FILES, owner, id_string, project
    )
    return survey


# pylint: disable=too-many-arguments, too-many-positional-arguments
def do_publish_xlsform(user, post, files, owner, id_string=None, project=None):
    """
    Publishes XLSForm.
    """
    if id_string and project:
        xform = get_object_or_404(
            XForm, user=owner, id_string=id_string, project=project
        )
        if not ManagerRole.user_has_role(user, xform):
            raise exceptions.PermissionDenied(
                _(f"{user} has no manager/owner role to the form {xform}")
            )
    elif not user.has_perm("can_add_xform", owner.profile):
        raise exceptions.PermissionDenied(
            detail=_(
                f"User {user.username} has no permission to add xforms to "
                f"account {owner.username}"
            )
        )

    def set_form():
        """
        Instantiates QuickConverter form to publish a form.
        """

        if project:
            args = dict(list(iteritems(post))) if post else {}
            args["project"] = project.pk
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
            "project": project.pk,
            "dropbox_xls_url": request.data.get("dropbox_xls_url"),
            "xls_url": request.data.get("xls_url"),
            "csv_url": request.data.get("csv_url"),
            "text_xls_form": request.data.get("text_xls_form"),
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
            XForm.objects.get(user=project.organization, id_string=xform.id_string)
        except XForm.DoesNotExist:
            return False
        return True

    if "formid" in request.data:
        xform = get_object_or_404(XForm, pk=request.data.get("formid"))
        safe_delete(f"{PROJ_OWNER_CACHE}{xform.project.pk}")
        safe_delete(f"{PROJ_FORMS_CACHE}{xform.project.pk}")
        safe_delete(f"{PROJ_BASE_FORMS_CACHE}{xform.project.pk}")
        safe_delete(f"{PROJ_NUM_DATASET_CACHE}{xform.project.pk}")
        safe_delete(f"{PROJ_SUB_DATE_CACHE}{xform.project.pk}")
        if not ManagerRole.user_has_role(request.user, xform):
            raise exceptions.PermissionDenied(
                _(f"{request.user} has no manager/owner role to the form {xform}")
            )

        msg = "Form with the same id_string already exists in this account"
        # Without this check, a user can't transfer a form to projects that
        # he/she owns because `id_string_exists_in_account` will always
        # return true
        if project.organization != xform.user and id_string_exists_in_account():
            raise exceptions.ParseError(_(msg))
        xform.user = project.organization
        xform.project = project

        try:
            with transaction.atomic():
                xform.save()
        except IntegrityError as e:
            raise exceptions.ParseError(_(msg)) from e
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

    if isinstance(xform, XForm):
        with use_master:
            # Ensure the cached project is the updated version.
            # Django lazy loads related objects as such we need to
            # ensure the project retrieved is up to date.
            reset_project_cache(xform.project, request, ProjectSerializer)
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
            _("You do not have permission to view data from this form.")
        )

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
        tags = form.cleaned_data.get("tags", None)

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
        if value.startswith("dataview"):
            model = DataView
        elif value.startswith("xform"):
            model = XForm
        elif value.startswith("entity_list"):
            model = EntityList

        if model:
            parts = value.split()
            if len(parts) > 1:
                name = parts[2] if len(parts) > 2 else None

                return (get_object_or_404(model, pk=parts[1]), name)

        return (None, None)

    if metadata.data_file:
        file_path = metadata.data_file.name
        filename, extension = os.path.splitext(file_path.split("/")[-1])
        extension = extension.strip(".")
        dfs = storages["default"]

        if dfs.exists(file_path):
            response = response_with_mimetype_and_name(
                metadata.data_file_type,
                filename,
                extension=extension,
                show_date=False,
                file_path=file_path,
                full_mime=True,
            )

            return response
        return HttpResponseNotFound()
    try:
        URLValidator()(metadata.data_value)
    except ValidationError:
        obj, filename = get_data_value_objects(metadata.data_value)
        if obj:
            if isinstance(obj, EntityList):
                return get_entity_list_export_response(request, obj, filename)

            export_type = get_metadata_format(metadata.data_value)
            dataview = obj if isinstance(obj, DataView) else False
            xform = obj.xform if isinstance(obj, DataView) else obj

            return custom_response_handler(
                request,
                xform,
                {},
                export_type,
                filename=filename,
                dataview=dataview,
                metadata=metadata,
            )

    return HttpResponseRedirect(metadata.data_value)


# pylint: disable=invalid-name
def check_inherit_permission_from_project(xform_id, user):
    """
    Checks if a user has the same project permissions for the given xform_id,
    if there is a difference applies the project permissions to the user for
    the given xform_id.
    """
    if xform_id == "public":
        return

    try:
        int(xform_id)
    except ValueError:
        return

    # get the project_xform
    xform = (
        XForm.objects.filter(pk=xform_id)
        .select_related("project")
        .only("project_id", "id")
        .first()
    )

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


def get_baseviewset_class():
    """
    Checks the setting if the default viewset is implementded otherwise loads
    the default in onadata
    :return: the default baseviewset
    """
    return (
        import_string(settings.BASE_VIEWSET)
        if settings.BASE_VIEWSET
        else DefaultBaseViewset
    )


def generate_tmp_path(uploaded_csv_file):
    """
    Write file to temporary folder if not already there
    :param uploaded_csv_file:
    :return: path to the tmp folder
    """
    if isinstance(uploaded_csv_file, InMemoryUploadedFile):
        uploaded_csv_file.open()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
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
    xform_user_obj_perm_qs = xform.xformuserobjectpermission_set.all()

    for perm in queryset_iterator(xform_user_obj_perm_qs):
        if perm.user not in data:
            user = perm.user

            # create default profile if missing
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=user)

            if is_organization(user.profile):
                org_members = get_team_members(user.username)

            data[user] = {
                "permissions": [],
                "is_org": is_organization(profile),
                "metadata": profile.metadata,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user": user.username,
            }
        if perm.user in data:
            data[perm.user]["permissions"].append(perm.permission.codename)

    for user in org_members:
        # create default profile if missing
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)

        if user not in data:
            data[user] = {
                "permissions": get_perms(user, xform),
                "is_org": is_organization(profile),
                "metadata": profile.metadata,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user": user.username,
            }

    for value in data.values():
        value["permissions"].sort()
        value["role"] = get_role(value["permissions"], xform)
        del value["permissions"]

    return data


def get_team_members(org_username):
    """Return members team if it exists else none.

    :param org_username: organization name
    :return: team
    """
    members = []
    try:
        team = Team.objects.get(name=f"{org_username}#{MEMBERS}")
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

    dataentry_role_list = [DataEntryMinorRole, DataEntryOnlyRole, DataEntryRole]
    dataentry_role = {role.name: role for role in dataentry_role_list}

    if metadata:
        meta_perms = metadata.data_value.split("|")

        # update roles
        users = get_xform_users(xform)

        for user in users:
            role = users.get(user).get("role")
            if role in editor_role:
                role = ROLES.get(meta_perms[0])
                role.add(user, xform)

            if role in dataentry_role:
                role = ROLES.get(meta_perms[1])
                role.add(user, xform)


def get_host_domain(request):
    """Get host from reques or check the Site model"""
    request_host = request and request.get_host()
    return request_host or Site.objects.get_current().domain


def replace_attachment_name_with_url(data, request):
    """Replaces the attachment filename with a URL in ``data`` object."""
    site_url = get_host_domain(request)

    for record in data:
        attachments: dict = record.json.get("_attachments")
        if attachments:
            attachment_details = [
                (attachment["name"], attachment["download_url"])
                for attachment in attachments
                if "download_url" in attachment
            ]
            question_keys = list(record.json.keys())
            question_values = list(record.json.values())

            for attachment_name, attachment_path in attachment_details:
                try:
                    index: int = question_values.index(attachment_name)
                    question_key: str = question_keys[index]
                    record.json[question_key] = site_url + attachment_path
                except ValueError:
                    pass
    return data


ENKETO_AUTH_COOKIE = getattr(settings, "ENKETO_AUTH_COOKIE", "__enketo")
ENKETO_META_UID_COOKIE = getattr(
    settings, "ENKETO_META_UID_COOKIE", "__enketo_meta_uid"
)
ENKETO_META_USERNAME_COOKIE = getattr(
    settings, "ENKETO_META_USERNAME_COOKIE", "__enketo_meta_username"
)


def set_enketo_signed_cookies(resp, username=None, json_web_token=None):
    """Set signed cookies for JWT token in the HTTPResponse resp object."""
    if not username and not json_web_token:
        return None

    max_age = 30 * 24 * 60 * 60 * 1000
    enketo_meta_uid = {"max_age": max_age, "salt": settings.ENKETO_API_SALT}
    enketo = {"secure": False, "salt": settings.ENKETO_API_SALT}

    # add domain attribute if ENKETO_AUTH_COOKIE_DOMAIN is set in settings
    # i.e. don't add in development environment because cookie automatically
    # assigns 'localhost' as domain
    if getattr(settings, "ENKETO_AUTH_COOKIE_DOMAIN", None):
        enketo_meta_uid["domain"] = settings.ENKETO_AUTH_COOKIE_DOMAIN
        enketo["domain"] = settings.ENKETO_AUTH_COOKIE_DOMAIN

    resp.set_signed_cookie(ENKETO_META_UID_COOKIE, username, **enketo_meta_uid)
    resp.set_signed_cookie(ENKETO_META_USERNAME_COOKIE, username, **enketo_meta_uid)
    resp.set_signed_cookie(ENKETO_AUTH_COOKIE, json_web_token, **enketo)

    return resp


def get_org_profile_cache_key(user, organization):
    """Return cache key given user and organization profile"""
    org_username = organization.user.username

    if user.is_anonymous:
        return f"{ORG_PROFILE_CACHE}{org_username}-anon"

    user_role = get_role_in_org(user, organization)

    return f"{ORG_PROFILE_CACHE}{org_username}-{user_role}"


def invalidate_organization_cache(org_username):
    """Set organization cache to none for all roles"""
    for role in ROLES_ORDERED:
        key = f"{ORG_PROFILE_CACHE}{org_username}-{role.name}"
        safe_delete(key)

    safe_delete(f"{ORG_PROFILE_CACHE}{org_username}-anon")


def _get_xform_list_cache_key_prefix(xform_or_project):
    """Get the cache key prefix for the XForm list by user's role

    :param xform_or_project: XForm or Project being accessed
    :return: cache key prefix based on role assigned to form/project
    """
    object_type = type(xform_or_project).__name__
    return f"{XFORM_LIST_CACHE}{xform_or_project.id}-{object_type}"


def get_xform_list_cache_key(user, xform_or_project):
    """Get the cache key for the XForm list by user's role

    :param user: User making request
    :param xform_or_project: XForm or Project being accessed
    :return: cache key based on role assigned to form/project
    """
    cache_key_prefix = _get_xform_list_cache_key_prefix(xform_or_project)
    anonymous_user_key = f"{cache_key_prefix}-anon"

    if user.is_anonymous:
        return anonymous_user_key

    perms = get_perms(user, xform_or_project)
    user_role = get_role(perms, xform_or_project)

    if user_role is None:
        return anonymous_user_key

    return f"{cache_key_prefix}-{user_role}"


def invalidate_xform_list_cache(xform):
    """Invalidate the cache for the XForm list by user's role

    :param xform: XForm instance
    :return: None
    """
    xform_cache_key_prefix = _get_xform_list_cache_key_prefix(xform)
    project_cache_key_prefix = _get_xform_list_cache_key_prefix(xform.project)

    for role in ROLES_ORDERED:
        safe_delete(f"{xform_cache_key_prefix}-{role.name}")
        safe_delete(f"{project_cache_key_prefix}-{role.name}")

    safe_delete(f"{xform_cache_key_prefix}-anon")
    safe_delete(f"{project_cache_key_prefix}-anon")
