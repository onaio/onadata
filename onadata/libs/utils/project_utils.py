from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.permissions import OwnerRole, ReadOnlyRole


def set_project_perms_to_xform(xform, project):
    if project.shared != xform.shared:
        xform.shared = project.shared
        xform.shared_data = project.shared
        xform.save()

    for perm in get_object_users_with_permissions(project):
        user = perm['user']

        if user != xform.created_by:
            ReadOnlyRole.add(user, xform)
        else:
            OwnerRole.add(user, xform)
