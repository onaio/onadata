# -*- coding: utf-8 -*-
"""
Project Serializer module.
"""
from six import itervalues

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.tools import (
    get_or_create_organization_owners_team,
    get_organization_members_team,
)
from onadata.apps.logger.models import Project, XForm
from onadata.libs.permissions import (
    ManagerRole,
    OwnerRole,
    ReadOnlyRole,
    get_role,
    is_organization,
)
from onadata.libs.serializers.dataview_serializer import DataViewMinimalSerializer
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.utils.analytics import track_object_event
from onadata.libs.utils.qrcode import generate_odk_qrcode
from onadata.libs.utils.cache_tools import (
    PROJ_BASE_FORMS_CACHE,
    PROJ_FORMS_CACHE,
    PROJ_NUM_DATASET_CACHE,
    PROJ_OWNER_CACHE,
    PROJ_PERM_CACHE,
    PROJ_SUB_DATE_CACHE,
    PROJ_TEAM_USERS_CACHE,
    PROJECT_LINKED_DATAVIEWS,
    safe_delete,
)
from onadata.libs.utils.decorators import check_obj

# pylint: disable=invalid-name
User = get_user_model()


def get_project_xforms(project):
    """
    Returns an XForm queryset from project. The prefetched
    `xforms_prefetch` or `xform_set.filter()` queryset.
    """
    return (
        project.xforms_prefetch
        if hasattr(project, "xforms_prefetch")
        else project.xform_set.filter(deleted_at__isnull=True)
    )


@check_obj
def get_last_submission_date(project):
    """Return the most recent submission date to any of the projects
    datasets.

    :param project: The project to find the last submission date for.
    """
    cache_key = f"{PROJ_SUB_DATE_CACHE}{project.pk}"
    last_submission_date = cache.get(cache_key)
    if last_submission_date:
        return last_submission_date
    xforms = get_project_xforms(project)
    dates = [
        x.last_submission_time for x in xforms if x.last_submission_time is not None
    ]
    dates.sort(reverse=True)
    last_submission_date = dates[0] if dates else None

    cache.set(cache_key, last_submission_date)

    return last_submission_date


@check_obj
def get_num_datasets(project):
    """Return the number of datasets attached to the project.

    :param project: The project to find datasets for.
    """
    project_cache_key = f"{PROJ_NUM_DATASET_CACHE}{project.pk}"
    count = cache.get(project_cache_key)
    if count:
        return count

    count = len(get_project_xforms(project))
    cache.set(project_cache_key, count)
    return count


def is_starred(project, request):
    """
    Return True if the request.user has starred this project.
    """
    return project.user_stars.filter(pk=request.user.pk).count() == 1


def get_team_permissions(team, project):
    """
    Return team permissions.
    """
    return project.projectgroupobjectpermission_set.filter(
        group__pk=team.pk
    ).values_list("permission__codename", flat=True)


@check_obj
def get_teams(project):
    """
    Return the teams with access to the project.
    """
    project_team_cache_key = f"{PROJ_TEAM_USERS_CACHE}{project.pk}"
    teams_users = cache.get(project_team_cache_key)
    if teams_users:
        return teams_users

    teams_users = []
    teams = project.organization.team_set.all()

    for team in teams:
        # to take advantage of prefetch iterate over user set
        users = [user.username for user in team.user_set.all()]
        perms = get_team_permissions(team, project)

        teams_users.append(
            {"name": team.name, "role": get_role(perms, project), "users": users}
        )

    cache.set(project_team_cache_key, teams_users)
    return teams_users


@check_obj
def get_users(project, context, all_perms=True):
    """
    Return a list of users and organizations that have access to the project.
    """
    project_permissions_cache_key = f"{PROJ_PERM_CACHE}{project.pk}"
    if all_perms:
        users = cache.get(project_permissions_cache_key)
        if users:
            return users

    data = {}

    request_user = context["request"].user

    if not request_user.is_anonymous:
        request_user_perms = [
            perm.permission.codename
            for perm in project.projectuserobjectpermission_set.filter(
                user=request_user
            )
        ]
        request_user_role = get_role(request_user_perms, project)
        request_user_is_admin = request_user_role in [OwnerRole.name, ManagerRole.name]
    else:
        request_user_is_admin = False

    for perm in project.projectuserobjectpermission_set.all():
        if perm.user_id not in data:
            user = perm.user

            if (
                all_perms
                or user in [request_user, project.organization]
                or request_user_is_admin
            ):
                data[perm.user_id] = {
                    "permissions": [],
                    "is_org": is_organization(user.profile),
                    "metadata": user.profile.metadata,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "user": user.username,
                }
        if perm.user_id in data:
            data[perm.user_id]["permissions"].append(perm.permission.codename)

    for k in list(data):
        data[k]["permissions"].sort()
        data[k]["role"] = get_role(data[k]["permissions"], project)
        del data[k]["permissions"]

    results = list(itervalues(data))

    if all_perms:
        cache.set(project_permissions_cache_key, results)

    return results


def set_owners_permission(user, project):
    """Give the user owner permission"""
    OwnerRole.add(user, project)


# pylint: disable=too-few-public-methods
class BaseProjectXFormSerializer(serializers.HyperlinkedModelSerializer):
    """
    BaseProjectXFormSerializer class.
    """

    formid = serializers.ReadOnlyField(source="id")
    name = serializers.ReadOnlyField(source="title")

    # pylint: disable=too-few-public-methods,missing-class-docstring
    class Meta:
        model = XForm
        fields = ("name", "formid", "id_string", "is_merged_dataset")


# pylint: disable=too-few-public-methods
class ProjectXFormSerializer(serializers.HyperlinkedModelSerializer):
    """
    ProjectXFormSerializer class - to return project xform info.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="xform-detail", lookup_field="pk"
    )
    formid = serializers.ReadOnlyField(source="id")
    name = serializers.ReadOnlyField(source="title")
    published_by_formbuilder = serializers.SerializerMethodField()

    # pylint: disable=too-few-public-methods,missing-class-docstring
    class Meta:
        model = XForm
        fields = (
            "name",
            "formid",
            "id_string",
            "num_of_submissions",
            "downloadable",
            "encrypted",
            "published_by_formbuilder",
            "last_submission_time",
            "date_created",
            "url",
            "last_updated_at",
            "is_merged_dataset",
        )

    def get_published_by_formbuilder(self, obj):  # pylint: disable=no-self-use
        """
        Returns true if the form was published by formbuilder.
        """
        metadata = obj.metadata_set.filter(data_type="published_by_formbuilder").first()
        return metadata and hasattr(metadata, "data_value") and metadata.data_value


class BaseProjectSerializer(serializers.HyperlinkedModelSerializer):
    """
    BaseProjectSerializer class.
    """

    projectid = serializers.ReadOnlyField(source="id")
    url = serializers.HyperlinkedIdentityField(
        view_name="project-detail", lookup_field="pk"
    )
    owner = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        source="organization",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    metadata = JsonField(required=False)
    starred = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    forms = serializers.SerializerMethodField()
    project_qrcode = serializers.SerializerMethodField()
    public = serializers.BooleanField(source="shared")
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField()
    last_submission_date = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "url",
            "projectid",
            "owner",
            "created_by",
            "metadata",
            "starred",
            "users",
            "forms",
            "public",
            "tags",
            "num_datasets",
            "last_submission_date",
            "teams",
            "name",
            "date_created",
            "date_modified",
            "deleted_at",
            "project_qrcode"
        ]

    def get_starred(self, obj):
        """
        Return True if request user has starred this project.
        """
        return is_starred(obj, self.context["request"])

    def get_users(self, obj):
        """
        Return a list of users and organizations that have access to the
        project.
        """
        owner_query_param_in_request = (
            "request" in self.context and "owner" in self.context["request"].GET
        )
        return get_users(obj, self.context, owner_query_param_in_request)

    @check_obj
    def get_forms(self, obj):
        """
        Return list of xforms in the project.
        """
        project_forms_cache_key = f"{PROJ_BASE_FORMS_CACHE}{obj.pk}"
        forms = cache.get(project_forms_cache_key)
        if forms:
            return forms

        xforms = get_project_xforms(obj)
        request = self.context.get("request")
        serializer = BaseProjectXFormSerializer(
            xforms, context={"request": request}, many=True
        )
        forms = list(serializer.data)
        cache.set(project_forms_cache_key, forms)

        return forms

    def get_num_datasets(self, obj):  # pylint: disable=no-self-use
        """
        Return the number of datasets attached to the project.
        """
        return get_num_datasets(obj)

    def get_project_qrcode(self, obj):  # pylint: disable=no-self-use
        """
        Return the project settings QR Code data uri.
        """
        request = self.context.get("request")
        return generate_odk_qrcode(request, None, 'projects', obj.pk)

    def get_last_submission_date(self, obj):  # pylint: disable=no-self-use
        """
        Return the most recent submission date to any of the projects datasets.
        """
        return get_last_submission_date(obj)

    def get_teams(self, obj):  # pylint: disable=no-self-use
        """
        Return the teams with access to the project.
        """
        return get_teams(obj)


def can_add_project_to_profile(user, organization):
    """
    Check if user has permission to add a project to a profile.
    """
    perms = "can_add_project"
    if (
        user != organization
        and not user.has_perm(perms, organization.profile)
        and not user.has_perm(perms, OrganizationProfile.objects.get(user=organization))
    ):
        return False

    return True


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    """
    ProjectSerializer class - creates and updates a project.
    """

    projectid = serializers.ReadOnlyField(source="id")
    url = serializers.HyperlinkedIdentityField(
        view_name="project-detail", lookup_field="pk"
    )
    owner = serializers.HyperlinkedRelatedField(
        view_name="user-detail",
        source="organization",
        lookup_field="username",
        queryset=User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ),
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name="user-detail", lookup_field="username", read_only=True
    )
    metadata = JsonField(required=False)
    starred = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    forms = serializers.SerializerMethodField()
    public = serializers.BooleanField(source="shared")
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField()
    project_qrcode = serializers.SerializerMethodField()
    last_submission_date = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()

    class Meta:
        model = Project
        exclude = ("shared", "user_stars", "deleted_by", "organization")

    def validate(self, attrs):
        """Validate the project name does not exist and the user has the permissions to
        create a project in the organization."""
        name = attrs.get("name")
        organization = attrs.get("organization")
        if not self.instance and organization:
            project_w_same_name = Project.objects.filter(
                name__iexact=name, organization=organization
            )
            if project_w_same_name:
                raise serializers.ValidationError(
                    {"name": _(f"Project {name} already exists.")}
                )
        else:
            organization = organization or self.instance.organization
        request = self.context["request"]
        try:
            has_perm = can_add_project_to_profile(request.user, organization)
        except OrganizationProfile.DoesNotExist:
            # most likely when transfering a project to an individual account
            # A user does not require permissions to the user's account forms.
            has_perm = False
        if not has_perm:
            raise serializers.ValidationError(
                {
                    "owner": _(
                        "You do not have permission to create a project "
                        f"in the organization {organization}."
                    )
                }
            )
        return attrs

    def validate_public(self, value):  # pylint: disable=no-self-use
        """
        Validate the public field
        """
        if not settings.ALLOW_PUBLIC_DATASETS and value:
            raise serializers.ValidationError(
                _("Public projects are currently disabled.")
            )
        return value

    def validate_metadata(self, value):  # pylint: disable=no-self-use
        """
        Validate metadaata is a valid JSON value.
        """
        msg = serializers.ValidationError(_("Invaid value for metadata"))
        try:
            json_val = JsonField.to_json(value)
        except ValueError as e:
            raise serializers.ValidationError(msg) from e
        else:
            if json_val is None:
                raise serializers.ValidationError(msg)
        return value

    def update(self, instance, validated_data):
        """Update project properties."""
        metadata = JsonField.to_json(validated_data.get("metadata"))
        if metadata is None:
            metadata = {}
        owner = validated_data.get("organization")

        if self.partial and metadata:
            if not isinstance(instance.metadata, dict):
                instance.metadata = {}

            instance.metadata.update(metadata)
            validated_data["metadata"] = instance.metadata

        if self.partial and owner:
            # give the new owner permissions
            set_owners_permission(owner, instance)

            if is_organization(owner.profile):
                owners_team = get_or_create_organization_owners_team(owner.profile)
                members_team = get_organization_members_team(owner.profile)
                OwnerRole.add(owners_team, instance)
                ReadOnlyRole.add(members_team, instance)
                owners = owners_team.user_set.all()
                # Owners are also members
                members = members_team.user_set.exclude(
                    username__in=[user.username for user in owners]
                )
                # Exclude new owner if in members
                members = members.exclude(username=owner.username)

                # Add permissions to all users in Owners and Members team
                for owner in owners:
                    OwnerRole.add(owner, instance)
                for member in members:
                    ReadOnlyRole.add(member, instance)

            # clear cache
            safe_delete(f"{PROJ_PERM_CACHE}{instance.pk}")

        project = super().update(instance, validated_data)

        project.xform_set.exclude(shared=project.shared).update(
            shared=project.shared, shared_data=project.shared
        )

        return instance

    @track_object_event(
        user_field="created_by",
        properties={
            "created_by": "created_by",
            "project_id": "pk",
            "project_name": "name",
        },
    )
    def create(self, validated_data):
        """Creates a project."""
        metadata = validated_data.get("metadata", {})
        if metadata is None:
            metadata = {}
        created_by = self.context["request"].user

        try:
            project = Project.objects.create(  # pylint: disable=no-member
                name=validated_data.get("name"),
                organization=validated_data.get("organization"),
                created_by=created_by,
                shared=validated_data.get("shared", False),
                metadata=metadata,
            )
        except IntegrityError as e:
            raise serializers.ValidationError(
                "The fields name, organization must make a unique set."
            ) from e
        else:
            project.xform_set.exclude(shared=project.shared).update(
                shared=project.shared, shared_data=project.shared
            )
            request = self.context.get("request")
            serializer = ProjectSerializer(project, context={"request": request})
            response = serializer.data
            cache.set(f"{PROJ_OWNER_CACHE}{project.pk}", response)
            return project

    def get_users(self, obj):  # pylint: disable=no-self-use
        """
        Return a list of users and organizations that have access to the
        project.
        """
        return get_users(obj, self.context)

    @check_obj
    def get_forms(self, obj):  # pylint: disable=no-self-use
        """
        Return list of xforms in the project.
        """
        project_forms_cache_key = f"{PROJ_FORMS_CACHE}{obj.pk}"
        forms = cache.get(project_forms_cache_key)
        if forms:
            return forms
        xforms = get_project_xforms(obj)
        request = self.context.get("request")
        serializer = ProjectXFormSerializer(
            xforms, context={"request": request}, many=True
        )
        forms = list(serializer.data)
        cache.set(project_forms_cache_key, forms)

        return forms

    def get_num_datasets(self, obj):  # pylint: disable=no-self-use
        """
        Return the number of datasets attached to the project.
        """
        return get_num_datasets(obj)

    def get_project_qrcode(self, obj):  # pylint: disable=no-self-use
        """
        Return the project settings QR Code data uri.
        """
        request = self.context["request"]
        return generate_odk_qrcode(request, None, 'projects', obj.pk)

    def get_last_submission_date(self, obj):  # pylint: disable=no-self-use
        """
        Return the most recent submission date to any of the projects datasets.
        """
        return get_last_submission_date(obj)

    def get_starred(self, obj):  # pylint: disable=no-self-use
        """
        Return True if request user has starred this project.
        """
        return is_starred(obj, self.context["request"])

    def get_teams(self, obj):  # pylint: disable=no-self-use
        """
        Return the teams with access to the project.
        """
        return get_teams(obj)

    @check_obj
    def get_data_views(self, obj):
        """
        Return a list of filtered datasets.
        """
        project_dataview_cache_key = f"{PROJECT_LINKED_DATAVIEWS}{obj.pk}"
        data_views = cache.get(project_dataview_cache_key)
        if data_views:
            return data_views

        data_views_obj = (
            obj.dataview_prefetch
            if hasattr(obj, "dataview_prefetch")
            else obj.dataview_set.filter(deleted_at__isnull=True)
        )

        serializer = DataViewMinimalSerializer(
            data_views_obj, many=True, context=self.context
        )
        data_views = list(serializer.data)

        cache.set(project_dataview_cache_key, data_views)

        return data_views
