# -*- coding: utf-8 -*-
"""
project_utils module - apply project permissions to a form.
"""
import sys
import requests

from typing import List, Optional, Tuple
from urllib.parse import urljoin
from django.conf import settings
from django.db import IntegrityError

from multidb.pinning import use_master

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models import MetaData
from onadata.celeryapp import app
from onadata.libs.permissions import (
    ROLES,
    OwnerRole,
    get_object_users_with_permissions,
    get_role,
    is_organization,
)
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME
from onadata.libs.utils.common_tools import report_exception


class ExternalServiceRequestError(Exception):
    pass


def get_project_users(project):
    """Return project users with the role assigned to them."""
    ret = {}

    for perm in project.projectuserobjectpermission_set.all():
        if perm.user.username not in ret:
            user = perm.user

            ret[user.username] = {
                "permissions": [],
                "is_org": is_organization(user.profile),
                "first_name": user.first_name,
                "last_name": user.last_name,
            }

        ret[perm.user.username]["permissions"].append(perm.permission.codename)

    for user, val in ret.items():
        val["role"] = get_role(val["permissions"], project)
        del val["permissions"]

    return ret


def set_project_perms_to_xform(xform, project):
    """
    Apply project permissions to a form, this usually happens when a new form
    is being published or it is being moved to a new project.
    """
    # allows us to still use xform.shared and xform.shared_data as before
    # only switch if xform.shared is False
    xform_is_shared = xform.shared or xform.shared_data
    if not xform_is_shared and project.shared != xform.shared:
        xform.shared = project.shared
        xform.shared_data = project.shared
        xform.save()

    # clear existing permissions
    for perm in get_object_users_with_permissions(xform, with_group_users=True):
        user = perm["user"]
        role_name = perm["role"]
        role = ROLES.get(role_name)
        if role and (user not in (xform.user, project.user, project.created_by)):
            role.remove_obj_permissions(user, xform)

    owners = project.organization.team_set.filter(
        name=f"{project.organization.username}#{OWNER_TEAM_NAME}",
        organization=project.organization,
    )

    if owners:
        OwnerRole.add(owners[0], xform)

    for perm in get_object_users_with_permissions(project, with_group_users=True):
        user = perm["user"]
        role_name = perm["role"]
        role = ROLES.get(role_name)

        if user == xform.created_by:
            OwnerRole.add(user, xform)
        else:
            if role:
                role.add(user, xform)


# pylint: disable=invalid-name
@app.task(bind=True, max_retries=3)
def set_project_perms_to_xform_async(self, xform_id, project_id):
    """
    Apply project permissions for ``project_id`` to a form ``xform_id`` task.
    """

    def _set_project_perms():
        try:
            xform = XForm.objects.get(id=xform_id)
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, XForm.DoesNotExist) as e:
            msg = (
                f"{type(e)}: Setting project {project_id} permissions to "
                f"form {xform_id} failed."
            )
            # make a report only on the 3rd try.
            if self.request.retries > 2:
                report_exception(msg, e, sys.exc_info())
            self.retry(countdown=60 * self.request.retries, exc=e)
        else:
            set_project_perms_to_xform(xform, project)

    try:
        if getattr(settings, "SLAVE_DATABASES", []):

            with use_master:
                _set_project_perms()
        else:
            _set_project_perms()
    except (Project.DoesNotExist, XForm.DoesNotExist) as e:
        # make a report only on the 3rd try.
        if self.request.retries > 2:
            msg = (
                f"{type(e)}: Setting project {project_id} permissions to "
                f"form {xform_id} failed."
            )
            report_exception(msg, e, sys.exc_info())
        # let's retry if the record may still not be available in read replica.
        self.retry(countdown=60 * self.request.retries)
    except IntegrityError:
        # Nothing to do, fail silently, permissions seems to have been applied
        # already.
        pass
    except Exception as e:  # pylint: disable=broad-except
        msg = (
            f"{type(e)}: Setting project {project_id} permissions to "
            f"form {xform_id} failed."
        )
        report_exception(msg, e, sys.exc_info())


def propagate_project_permissions(project_id: int, headers: Optional[dict] = None) -> None:
    """
    Propagates Project permissions to external services(KPI)
    """
    if getattr(settings, "PROPAGATE_PERMISSIONS", False) and getattr(
        settings, "KPI_SERVICE_URL", None
    ):
        service_url = settings["KPI_SERVICE_URL"]
        session = requests.session()
        if headers:
            session.headers.update(headers)

        project: Project = Project.objects.get(id=project_id)
        users: dict[str, dict] = get_project_users(project)
        collaborators: List[Tuple[str, str]] = [
            (username, str(data.get("role")))
            for username, data in users.items()
            if data.get("role") != "owner" and data.get("role") in ["editor"]
        ]
        form_ids: List[int] = list(
            project.xform_set.filter(deleted_at__isnull=True).values_list(
                "id", flat=True
            )
        )

        # Propagate permissions for XForms that were published by
        # Formbuilder
        for form_id in form_ids:
            if (
                MetaData.objects.filter(
                    object_id=form_id,
                    data_type="published_by_formbuilder",
                    data_value=True,
                ).count()
                > 0
            ):
                form: str = XForm.objects.get(id=form_id).id_string
                asset_url = urljoin(
                    service_url, f"/api/v2/assets/{form}/permission-assignments/bulk/"
                )
                payload = [
                    {
                        "user": urljoin(service_url, f"/api/v2/users/{username}"),
                        "permission": urljoin(
                            service_url, "/api/v2/permissions/change_asset/"
                        ),
                    }
                    for username, _ in collaborators
                ]
                resp = session.post(asset_url, json=json.dumps(payload))
                if resp.status_code != 200:
                    raise ExternalServiceRequestError(
                        f"Failed to propagate permissions for {form}: {resp.status_code}"
                    )
