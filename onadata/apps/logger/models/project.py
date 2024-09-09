# -*- coding: utf-8 -*-
"""
Project model class
"""
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Prefetch
from django.db.models.signals import post_save
from django.utils import timezone

from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model
from taggit.managers import TaggableManager

from onadata.libs.models.base_model import BaseModel
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME

# pylint: disable=invalid-name
User = get_user_model()


# pylint: disable=too-few-public-methods
class PrefetchManager(models.Manager):
    """Project prefetched manager - prefetches models related to the Project model."""

    def get_queryset(self):
        """Return a queryset with the XForm, Team, tags, and other related relations
        prefetched."""
        # pylint: disable=invalid-name
        Team = apps.get_model("api", "Team")  # noqa N806
        XForm = apps.get_model("logger", "XForm")  # noqa N806

        # pylint: disable=no-member
        return (
            super()
            .get_queryset()
            .select_related("created_by", "organization")
            .prefetch_related(
                Prefetch(
                    "xform_set",
                    queryset=XForm.objects.filter(deleted_at__isnull=True)
                    .select_related("user")
                    .prefetch_related("user")
                    .prefetch_related("dataview_set")
                    .prefetch_related("metadata_set")
                    .only(
                        "id",
                        "user",
                        "project",
                        "title",
                        "date_created",
                        "last_submission_time",
                        "num_of_submissions",
                        "downloadable",
                        "id_string",
                        "is_merged_dataset",
                    ),
                    to_attr="xforms_prefetch",
                )
            )
            .prefetch_related("tags")
            .prefetch_related(
                Prefetch(
                    "projectuserobjectpermission_set",
                    queryset=ProjectUserObjectPermission.objects.select_related(
                        "user__profile__organizationprofile", "permission"
                    ),
                )
            )
            .prefetch_related(
                Prefetch(
                    "projectgroupobjectpermission_set",
                    queryset=ProjectGroupObjectPermission.objects.select_related(
                        "group", "permission"
                    ),
                )
            )
            .prefetch_related("user_stars")
            .prefetch_related(
                Prefetch(
                    "organization__team_set",
                    queryset=Team.objects.all().prefetch_related("user_set"),
                )
            )
        )


class Project(BaseModel):
    """
    Project model class
    """

    name = models.CharField(max_length=255)
    # pylint: disable=no-member
    metadata = models.JSONField(default=dict)
    organization = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="project_org", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="project_owner", on_delete=models.CASCADE
    )
    user_stars = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="project_stars"
    )
    shared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(
        User,
        related_name="project_deleted_by",
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )

    objects = models.Manager()
    tags = TaggableManager(related_name="project_tags")
    prefetched = PrefetchManager()

    class Meta:
        app_label = "logger"
        unique_together = (("name", "organization"),)
        permissions = (
            ("add_project_xform", "Can add xform to project"),
            ("report_project_xform", "Can make submissions to the project"),
            ("transfer_project", "Can transfer project to different owner"),
            ("can_export_project_data", "Can export data in project"),
            ("view_project_all", "Can view all associated data"),
            ("view_project_data", "Can view submitted data"),
            ("add_project_entitylist", "Can add entitylist to project"),
        )
        indexes = [
            models.Index(fields=["deleted_at"], name="idx_logger_project_deleted_at"),
        ]

    def __str__(self):
        return f"{self.organization}|{self.name}"

    def clean(self):
        """
        Raises a validation error if a project with same name and organization exists.
        """
        query_set = Project.objects.exclude(pk=self.pk).filter(
            name__iexact=self.name, organization=self.organization
        )
        if query_set.exists():
            raise ValidationError(
                f'Project name "{self.name.lower()}" is already in'
                " use in this account."
            )

    @property
    def user(self):
        """Returns the user who created the project."""
        return self.created_by

    @transaction.atomic()
    def soft_delete(self, user=None):
        """
        Soft deletes a project by adding a deleted_at timestamp and renaming
        the project name by adding a deleted-at and timestamp.
        Also soft deletes the associated forms.
        :return:
        """

        soft_deletion_time = timezone.now()
        deletion_suffix = soft_deletion_time.strftime("-deleted-at-%s")
        self.deleted_at = soft_deletion_time
        self.name += deletion_suffix
        if user is not None:
            self.deleted_by = user
        self.save()

        for form in self.xform_set.all():
            form.soft_delete(user=user)


# pylint: disable=unused-argument
def set_object_permissions(sender, instance=None, created=False, **kwargs):
    """Sets permissions to users who are owners of the organization."""
    if created:
        for perm in get_perms_for_model(Project):
            assign_perm(perm.codename, instance.organization, instance)

            owners = instance.organization.team_set.filter(
                name=f"{instance.organization.username}#{OWNER_TEAM_NAME}",
                organization=instance.organization,
            )
            for owner in owners:
                assign_perm(perm.codename, owner, instance)

            if owners:
                for user in owners[0].user_set.all():
                    assign_perm(perm.codename, user, instance)
            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


post_save.connect(
    set_object_permissions,
    sender=Project,
    dispatch_uid="set_project_object_permissions",
)


# pylint: disable=too-few-public-methods
class ProjectUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(Project, on_delete=models.CASCADE)


# pylint: disable=too-few-public-methods
class ProjectGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(Project, on_delete=models.CASCADE)
