from celery import task

from onadata.apps.logger.models import Project, XForm
from onadata.libs.permissions import (ROLES, OwnerRole,
                                      get_object_users_with_permissions)
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME


def set_project_perms_to_xform(xform, project):
    # allows us to still use xform.shared and xform.shared_data as before
    # only switch if xform.shared is False
    xform_is_shared = xform.shared or xform.shared_data
    if not xform_is_shared and project.shared != xform.shared:
        xform.shared = project.shared
        xform.shared_data = project.shared
        xform.save()

    # clear existing permissions
    for perm in get_object_users_with_permissions(
            xform, with_group_users=True):
        user = perm['user']
        role_name = perm['role']
        role = ROLES.get(role_name)
        if role and (user != xform.user and project.user != user and
                     project.created_by != user):
            role._remove_obj_permissions(user, xform)

    owners = project.organization.team_set.filter(
        name="{}#{}".format(project.organization.username, OWNER_TEAM_NAME),
        organization=project.organization)

    if owners:
        OwnerRole.add(owners[0], xform)

    for perm in get_object_users_with_permissions(
            project, with_group_users=True):
        user = perm['user']
        role_name = perm['role']
        role = ROLES.get(role_name)

        if user == xform.created_by:
            OwnerRole.add(user, xform)
        else:
            if role:
                role.add(user, xform)


@task
def set_project_perms_to_xform_async(xform_id, project_id):
    try:
        xform = XForm.objects.get(id=xform_id)
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, XForm.DoesNotExist):
        pass
    else:
        set_project_perms_to_xform(xform, project)
