# -*- coding: utf-8 -*-
"""The accounts that own what a gated action touches.

Each helper is a generator, so the related rows it reads are fetched only
when a gate needs the owners.
"""

from onadata.apps.logger.models import Instance, Project, XForm


def project_owners(project):
    """The account owning ``project``."""
    yield project.organization_id


def form_owners(xform):
    """The accounts owning ``xform``: its own and its project's."""
    yield xform.user_id
    yield xform.project.organization_id


def content_owners(content_object):
    """The accounts owning a form, project or submission."""
    if isinstance(content_object, XForm):
        yield from form_owners(content_object)
    elif isinstance(content_object, Project):
        yield from project_owners(content_object)
    elif isinstance(content_object, Instance):
        yield from form_owners(content_object.xform)


def team_holding_owners(teams):
    """The accounts owning each project and form ``teams`` hold a role on.

    Joining or moving a team hands its roles on, so an organisation whose
    project or form a team holds a role on governs that too, whichever
    organisation the team belongs to."""
    yield from (
        Project.objects.filter(
            projectgroupobjectpermission__group__in=teams, deleted_at__isnull=True
        )
        .values_list("organization_id", flat=True)
        .distinct()
    )
    for user_id, organization_id in (
        XForm.objects.filter(
            xformgroupobjectpermission__group__in=teams, deleted_at__isnull=True
        )
        .values_list("user_id", "project__organization_id")
        .distinct()
    ):
        yield user_id
        yield organization_id


def team_owners(team):
    """The account owning ``team``, and the owners of what it holds roles on."""
    yield team.organization_id
    yield from team_holding_owners((team,))
