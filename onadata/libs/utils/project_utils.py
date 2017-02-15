from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.permissions import OwnerRole
from onadata.libs.permissions import ROLES
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME


def set_project_perms_to_xform(xform, project):
    # allows us to still use xform.shared and xform.shared_data as before
    # only switch if xform.shared is False
    xform_is_shared = xform.shared or xform.shared_data
    if not xform_is_shared and project.shared != xform.shared:
        xform.shared = project.shared
        xform.shared_data = project.shared
        xform.save()

    owners = project.organization.team_set.filter(name="{}#{}".format(
        project.organization.username, OWNER_TEAM_NAME),
        organization=project.organization)

    if owners:
        OwnerRole.add(owners[0], xform)

    for perm in get_object_users_with_permissions(project,
                                                  with_group_users=True):
        user = perm['user']
        role_name = perm['role']
        role = ROLES.get(role_name)

        if user != xform.created_by:
            role.add(user, xform)
        else:
            OwnerRole.add(user, xform)
