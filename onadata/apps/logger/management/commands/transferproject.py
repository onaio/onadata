# -*- coding: utf-8 -*-
"""Functionality to transfer a project from one owner to another."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from onadata.apps.api.models import Team
from onadata.apps.api.models.organization_profile import get_organization_members_team
from onadata.apps.logger.models import MergedXForm, Project, XForm
from onadata.apps.logger.models.project import (
    set_object_permissions as set_project_permissions,
)
from onadata.libs.permissions import ReadOnlyRole
from onadata.libs.utils.project_utils import set_project_perms_to_xform


class Command(BaseCommand):
    """
    Command to transfer a project from one user to the other.

    Usage:
    The mandatory arguments are --current-owner, --new-owner and either of
    --project-id or --all-projects.
    Depending on what is supplied for --project-id or --all-projects,
    the command will either transfer a single project or all the projects.
    """

    help = "A command to reassign a project(s) from one user to the other."

    errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--current-owner",
            dest="current_owner",
            type=str,
            help="Username of the current owner of the project(s)",
        )
        parser.add_argument(
            "--new-owner",
            dest="new_owner",
            type=str,
            help="Username of the new owner of the project(s)",
        )
        parser.add_argument(
            "--project-id",
            dest="project_id",
            type=int,
            help="Id of the project to be transferred.",
        )
        parser.add_argument(
            "--all-projects",
            dest="all_projects",
            action="store_true",
            help="Supply this command if all the projects are to be"
            " transferred. If not, do not include the argument",
        )

    def get_user(self, username):
        """Return user object with the given username."""
        user_model = get_user_model()
        user = None
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.errors.append(f"User {username} does not exist")
        return user

    def _transfer_xform(self, project, to_user):
        """Transfer XForm to the new owner."""
        xforms = XForm.objects.filter(
            project=project, deleted_at__isnull=True, downloadable=True
        )
        for form in xforms:
            form.user = to_user
            form.created_by = to_user
            form.save()
            set_project_perms_to_xform(form, project)

    def _transfer_merged_xform(self, project, to_user):
        """Transfer MergedXForm to the new owner."""
        merged_xforms = MergedXForm.objects.filter(
            project=project, deleted_at__isnull=True
        )
        for form in merged_xforms:
            form.user = to_user
            form.created_by = to_user
            form.save()
            set_project_perms_to_xform(form, project)

    def transfer_project(self, project, to_user):
        """Transfer Project to the new owner."""
        project.organization = to_user
        project.created_by = to_user
        project.save()

        set_project_permissions(Project, project, created=True)

        if hasattr(to_user, "profile") and hasattr(
            to_user.profile, "organizationprofile"
        ):
            # Give readonly permission to members
            organization = to_user.profile.organizationprofile
            owners_team = Team.objects.get(
                name=f"{to_user.username}#{Team.OWNER_TEAM_NAME}", organization=to_user
            )
            members_team = get_organization_members_team(organization)

            ReadOnlyRole.add(members_team, project)

            # Owners are also members so we exclude them
            members = members_team.user_set.exclude(
                username__in=[user.username for user in owners_team.user_set.all()]
            )

            for member in members:
                ReadOnlyRole.add(member, project)

        self._transfer_xform(project, to_user)
        self._transfer_merged_xform(project, to_user)

    @transaction.atomic()
    def handle(self, *args, **options):
        """Transfer projects from one user to another."""
        from_user = self.get_user(options["current_owner"])
        to_user = self.get_user(options["new_owner"])

        if self.errors:
            self.stdout.write("".join(self.errors))
            return

        project_id = options.get("project_id")
        transfer_all_projects = options.get("all_projects")

        # No need to validate project ownership as they filtered
        # against current_owner
        projects = []
        if transfer_all_projects:
            projects = Project.objects.filter(
                organization=from_user, deleted_at__isnull=True
            )
        else:
            projects = Project.objects.filter(id=project_id, organization=from_user)

        for project in projects:
            self.transfer_project(project, to_user)

        self.stdout.write("Projects transferred successfully")
