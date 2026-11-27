# -*- coding: utf-8 -*-
"""Which owner and manager roles a share, a team or organisation join, a
form move or a meta permissions write hands out, and to whom."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q

from guardian.shortcuts import get_perms

from onadata.apps.logger.models import Project, XForm
from onadata.apps.logger.models.project import ProjectGroupObjectPermission
from onadata.apps.logger.models.xform import XFormGroupObjectPermission
from onadata.apps.main.models import MetaData
from onadata.libs.permissions import (
    ROLES,
    ManagerRole,
    OwnerRole,
    get_role,
    get_team_project_default_permissions,
)
from onadata.libs.stepup.policy import ADMIN_ROLE_NAMES
from onadata.libs.utils.common_tags import XFORM_META_PERMS
from onadata.libs.utils.project_utils import get_project_users
from onadata.libs.utils.xform_utils import (
    get_xform_users,
    meta_perms_roles,
    role_under_meta_perms,
    roles_under_meta_perms,
)


def _stored_meta_perms(xforms):
    """Each of ``xforms``' stored meta permissions values, keyed by form pk,
    read in one query."""
    return _stored_meta_perms_of([xform.pk for xform in xforms])


def _stored_meta_perms_of(xform_pks):
    stored = {}
    for object_id, value in MetaData.objects.filter(
        content_type=ContentType.objects.get_for_model(XForm),
        object_id__in=xform_pks,
        data_type=XFORM_META_PERMS,
    ).values_list("object_id", "data_value"):
        stored.setdefault(object_id, []).append(value)
    return stored


def admin_roles_granted(xforms, role_name, stored=None):
    """``(xform, role)`` for each owner or manager role that sharing ``xforms``
    as ``role_name`` grants.

    A form's meta permissions can turn a lesser role into an admin one, so a
    gate that read only ``role_name`` would let an editor share through.
    ``stored`` is ``_stored_meta_perms`` of ``xforms``, when already read.
    """
    xforms = list(xforms)
    if stored is None:
        stored = _stored_meta_perms(xforms)
    return [
        (xform, ROLES[name])
        for xform in xforms
        for name in sorted(roles_under_meta_perms(stored.get(xform.pk, ()), role_name))
        if name in ADMIN_ROLE_NAMES
    ]


def grants_admin_role(xforms, role_name):
    """Whether sharing ``xforms`` as ``role_name`` grants an owner or manager
    role on any of them."""
    return role_name in ADMIN_ROLE_NAMES or bool(admin_roles_granted(xforms, role_name))


def admin_role(role_name):
    """The owner or manager role named ``role_name``, or None for any other
    role."""
    return ROLES[role_name] if role_name in ADMIN_ROLE_NAMES else None


def holds_roles(user, granted):
    """Whether ``user`` already holds every ``(obj, role)`` in ``granted``, so
    a share granting them hands out nothing new."""
    return all(role.user_has_role(user, obj) for obj, role in granted)


def appoints_admins(xform, meta_perms):
    """Whether applying ``meta_perms`` to ``xform`` makes one of its current
    users an owner or manager they are not yet.

    Applying them re-assigns every user of the form, so writing back an
    unchanged value still promotes anyone who reached a slot's role since the
    value was last applied."""
    for user, details in get_xform_users(xform).items():
        name = role_under_meta_perms(meta_perms, details["role"])
        if name in ADMIN_ROLE_NAMES and not ROLES[name].user_has_role(user, xform):
            return True
    return False


def reapplying_appoints_admins(xforms):
    """Whether re-applying the stored meta permissions of any of ``xforms``
    makes one of its users an owner or manager they are not yet."""
    return any(
        appoints_admins(xform, meta_perms)
        for xform in xforms
        for meta_perms in xform.metadata_set.filter(
            data_type=XFORM_META_PERMS
        ).values_list("data_value", flat=True)
    )


def _admin_object_pks(permission_model, model, teams):
    """A query of the pks of the ``model`` objects, not deleted, that one of
    ``teams`` owns or manages outright.

    A manager's permissions are a subset of an owner's, so holding every one
    of them finds both."""
    codenames = set(ManagerRole.class_to_permissions[model])
    return (
        permission_model.objects.filter(
            group__in=teams,
            content_object__deleted_at__isnull=True,
            permission__codename__in=codenames,
        )
        .order_by()
        .values("group_id", "content_object_id")
        .annotate(held=Count("permission__codename", distinct=True))
        .filter(held=len(codenames))
        .values_list("content_object_id", flat=True)
    )


def _reaches_admin(codenames, model, stored=()):
    """Whether holding ``codenames`` on a ``model`` object, whose stored meta
    permissions are ``stored``, makes the holder an owner or manager."""
    return any(
        name in ADMIN_ROLE_NAMES
        for name in roles_under_meta_perms(stored, get_role(codenames, model))
    )


def _raised_xform_pks(teams):
    """The pks of the forms, not deleted, whose meta permissions turn a role
    one of ``teams`` holds into owner or manager."""
    with_meta_perms = MetaData.objects.filter(
        content_type=ContentType.objects.get_for_model(XForm),
        data_type=XFORM_META_PERMS,
    ).values("object_id")
    held = {}
    for team_pk, xform_pk, codename in XFormGroupObjectPermission.objects.filter(
        group__in=teams,
        content_object__deleted_at__isnull=True,
        content_object_id__in=with_meta_perms,
    ).values_list("group_id", "content_object_id", "permission__codename"):
        held.setdefault((team_pk, xform_pk), set()).add(codename)
    if not held:
        return set()
    stored = _stored_meta_perms_of({xform_pk for _team, xform_pk in held})
    return {
        xform_pk
        for (_team, xform_pk), codenames in held.items()
        if _reaches_admin(codenames, XForm, stored.get(xform_pk, ()))
    }


def team_admin_objects(teams):
    """Querysets of the projects and the forms, not deleted, that ``teams``
    own or manage, and so that joining one of them makes someone an admin of.

    A team may hold that role outright, or hold one that a form's meta
    permissions turn into owner or manager."""
    teams = list(teams)
    projects = Project.objects.filter(
        pk__in=_admin_object_pks(ProjectGroupObjectPermission, Project, teams)
    )
    xforms = XForm.objects.filter(
        Q(pk__in=_admin_object_pks(XFormGroupObjectPermission, XForm, teams))
        | Q(pk__in=_raised_xform_pks(teams))
    )
    return projects, xforms


def team_reaches_admin_role(team):
    """Whether joining ``team`` leads to owning or managing a project or form
    that is not deleted."""
    teams = (team,)
    return (
        _admin_object_pks(ProjectGroupObjectPermission, Project, teams).exists()
        or _admin_object_pks(XFormGroupObjectPermission, XForm, teams).exists()
        or bool(_raised_xform_pks(teams))
    )


def move_appoints_admins(xform, project):
    """Whether moving ``xform`` into ``project`` makes someone an owner or
    manager of it who is not one of ``project``.

    The move gives the form the project's roles, then applies the form's meta
    permissions to them."""
    teams = {
        perm.group
        for perm in project.projectgroupobjectpermission_set.select_related("group")
    }
    roles = {details["role"] for details in get_project_users(project).values()} | {
        get_role(get_perms(team, project), project) for team in teams
    }
    return any(
        name in ADMIN_ROLE_NAMES
        for role in roles - ADMIN_ROLE_NAMES
        for name in meta_perms_roles(xform, role)
    )


def _role_shared_with_member(members_team, project, user, role_name):
    if role_name == OwnerRole.name:
        return role_name
    if role_name == ManagerRole.name and project.created_by == user:
        return role_name
    return get_team_project_default_permissions(members_team, project)


def member_admin_roles(projects, members_team, user, role_name):
    """``(obj, role)`` for each owner or manager role that adding ``user`` to
    an organisation as ``role_name`` shares with them on ``projects``, the
    organisation's projects.

    Mirrors ``add_user_to_organization``, which also runs for an existing
    member. Each project is shared at the members team's role on it. An owner
    gets ``role_name`` on every project, and a manager gets it on the projects
    they created."""
    projects = list(projects.prefetch_related("xform_set"))
    stored = _stored_meta_perms(
        [xform for project in projects for xform in project.xform_set.all()]
    )
    granted = []
    for project in projects:
        shared = _role_shared_with_member(members_team, project, user, role_name)
        role = admin_role(shared)
        if role is not None:
            granted.append((project, role))
        granted.extend(
            admin_roles_granted(project.xform_set.all(), shared, stored=stored)
        )
    return granted
