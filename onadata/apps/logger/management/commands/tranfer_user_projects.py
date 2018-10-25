#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8
"""Command transfer_user_projects module.

Transfer projects to a different user/organization account.
- [ ] Reassign created_by and organization to the new owner/organization.
- [ ] Reassign all XForms under the user or project to the new.
      owner/organization. Updating the fields `user` and `created_by`.
- [ ] Apply project and form permissions to the new user.
- [ ] Remove project and form permissions from the old user?
"""


from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext_lazy

from guardian.shortcuts import assign_perm, get_perms_for_model

from onadata.apps.logger.models import Project
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME


def apply_perms(project):
    """Apply owner permissions of a project to the owners of the project."""
    for perm in get_perms_for_model(Project):
        assign_perm(perm.codename, project.organization, project)
        owners = project.organization.team_set.filter(
            name="{}#{}".format(
                project.organization.username, OWNER_TEAM_NAME
            ),
            organization=project.organization,
        )
        for owner in owners:
            assign_perm(perm.codename, owner, project)
        if owners:
            for user in owners[0].user_set.all():
                assign_perm(perm.codename, user, project)
        if project.created_by:
            assign_perm(perm.codename, project.created_by, project)


def move_project(from_user, to_user):
    """Trnsfer all projects and forms from_user to to_user.

    Arguments:
    ---------
    from_user - user or organization to transfer projects or forms from.
    to_user - user or organization to transfer projects or forms to.
    """
    for project in from_user.project_org.all():
        project.xform_set.all().update(user=to_user, created_by=to_user)
        project.organization = to_user
        project.created_by = to_user
        project.save()
        apply_perms(project)


class Command(BaseCommand):
    """Transfer projects to a different user/organization account."""

    help = ugettext_lazy(
        "Transfer user projects to a different user/organization account."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "from",
            help=ugettext_lazy(
                "User/Organization to transfer the project from."
            ),
        )
        parser.add_argument(
            "to",
            help=ugettext_lazy(
                "User/Organization to transfer the project to."
            ),
        )

    def handle(self, *args, **kwargs):
        try:
            from_user = User.objects.get(username=kwargs["from"])
        except User.DoesNotExist:
            self.stderr.write(
                ugettext_lazy(
                    "User with username {} is not known!".format(
                        kwargs["from"]
                    )
                )
            )
        else:
            try:
                to_user = User.objects.get(username=kwargs["to"])
            except User.DoesNotExist:
                self.stderr.write(
                    ugettext_lazy(
                        "User with username {} is not known!".format(
                            kwargs["to"]
                        )
                    )
                )
            else:
                move_project(from_user, to_user)
