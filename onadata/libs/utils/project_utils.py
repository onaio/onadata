# -*- coding: utf-8 -*-
"""
project_utils module - apply project permissions to a form.
"""

import re
import sys
from typing import Dict, List, Optional
from urllib.parse import urljoin

from django.conf import settings
from django.db.models import Q

import jwt
import requests
from multidb.pinning import use_master
from requests.adapters import Retry
from requests.sessions import HTTPAdapter

from onadata.apps.api.models.team import Team
from onadata.apps.logger.models.project import Project
from onadata.celeryapp import app
from onadata.libs.permissions import (
    get_role,
    is_organization,
)
from onadata.libs.utils.common_tags import (
    API_TOKEN,
    ONADATA_KOBOCAT_AUTH_HEADER,
)
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.model_tools import queryset_iterator


class ExternalServiceRequestError(Exception):
    """
    Custom Exception class for External service requests i.e Formbuilder
    """


def get_project_users(project):
    """Return project users with the role assigned to them."""
    ret = {}
    project_user_obj_perm_qs = project.projectuserobjectpermission_set.all()

    for perm in queryset_iterator(project_user_obj_perm_qs):
        if perm.user.username not in ret:
            user = perm.user

            ret[user.username] = {
                "permissions": [],
                "is_org": hasattr(user, "profile") and is_organization(user.profile),
                "first_name": user.first_name,
                "last_name": user.last_name,
            }

        ret[perm.user.username]["permissions"].append(perm.permission.codename)

    for user, val in ret.items():
        val["role"] = get_role(val["permissions"], project)
        del val["permissions"]

    return ret


def retrieve_asset_permissions(
    service_url: str, asset_id: str, session: requests.Session
) -> Dict[str, List[str]]:
    """
    Retrieves the currently assigned asset permissions for each user on KPI
    """
    ret = {}
    resp = session.get(
        urljoin(service_url, f"/api/v2/assets/{asset_id}/permission-assignments/")
    )
    if resp.status_code != 200:
        raise ExternalServiceRequestError(
            "Failed to retrieve current asset permission "
            f"assignments for {asset_id}: {resp.status_code}"
        )

    data = resp.json()
    for permission in data:
        user = permission.get("user")
        user = re.findall(r"\S\/api\/v2\/users\/(\w+)", user)[0]

        if user not in ret:
            ret[user] = []
        ret[user].append(permission.get("url"))
    return ret


def assign_change_asset_permission(
    service_url: str, asset_id: str, usernames: List[str], session: requests.Session
) -> requests.Response:
    """
    Bulk assigns the `change_asset` permission to a group of users on KPI
    """
    asset_url = urljoin(
        service_url, f"/api/v2/assets/{asset_id}/permission-assignments/bulk/"
    )
    payload = [
        {
            "user": urljoin(service_url, f"/api/v2/users/{username}/"),
            "permission": urljoin(service_url, "/api/v2/permissions/change_asset/"),
        }
        for username in usernames
    ]
    resp = session.post(asset_url, json=payload)
    if resp.status_code != 200:
        raise ExternalServiceRequestError(
            f"Failed to assign permissions for {asset_id}: {resp.status_code}"
        )
    return resp


@app.task(bind=True, max_retries=3)
def propagate_project_permissions_async(self, project_id: int):
    """
    Ensure that all project permissions are in sync with Formbuilder
    permissions
    """
    with use_master:
        project = Project.objects.get(id=project_id)
        try:
            propagate_project_permissions(project)
        except ExternalServiceRequestError as exc:
            if self.request.retries > 3:
                msg = f"Failed to propagate permissions for Project {project.pk}"
                report_exception(msg, exc, sys.exc_info())
            self.retry(exc=exc, countdown=60 * self.requests.retries)


def propagate_project_permissions(
    project: Project, headers: Optional[dict] = None, use_asset_owner_auth: bool = True
) -> None:
    """
    Propagates Project permissions to external services(KPI)
    """
    if getattr(settings, "KPI_INTERNAL_SERVICE_URL", None):
        service_url = settings.KPI_INTERNAL_SERVICE_URL

        # Create request session for the Internal KPI calls
        session = requests.session()
        session.mount(
            "http",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=2,
                    allowed_methods=["GET", "POST", "DELETE"],
                    status_forcelist=[502, 503, 504],
                )
            ),
        )

        if headers:
            session.headers.update(headers)

        # Retrieve users who have access to the project
        collaborators: List[str] = [
            username
            for username, data in get_project_users(project).items()
            if not data.get("is_org") and data.get("role") in ["manager", "owner"]
        ]

        if is_organization(project.organization.profile):
            owners_team = Team.objects.get(
                name=f"{project.organization.username}#{Team.OWNER_TEAM_NAME}"
            )
            owners_team = list(
                owners_team.user_set.filter(
                    ~Q(username=project.organization.username)
                ).values_list("username", flat=True)
            )
            collaborators += owners_team
            collaborators = list(set(collaborators))

        # Propagate permissions for XForms that were published by
        # Formbuilder
        for asset in project.xform_set.filter(deleted_at__isnull=True).iterator():
            if (
                asset.metadata_set.filter(
                    data_type="published_by_formbuilder", data_value=True
                ).count()
                == 0
            ):
                continue

            if use_asset_owner_auth:
                session.headers.update(
                    {
                        ONADATA_KOBOCAT_AUTH_HEADER: jwt.encode(
                            {API_TOKEN: asset.created_by.auth_token.key},
                            getattr(settings, "JWT_SECRET_KEY", "jwt"),
                            algorithm=getattr(settings, "JWT_ALGORITHM", "HS256"),
                        )
                    }
                )

            assigned_permissions = retrieve_asset_permissions(
                service_url, asset.id_string, session
            )
            new_users = [
                username
                for username in collaborators
                if username not in assigned_permissions
            ]
            removed_permissions = [
                (username, permissions)
                for username, permissions in assigned_permissions.items()
                if username not in collaborators
            ]

            # Unassign permissions granted to users who no longer have permissions
            for _, permission_assignments in removed_permissions:
                _ = [
                    session.delete(permission_assignment)
                    for permission_assignment in permission_assignments
                ]

            # Assign permissions to the new users
            if new_users:
                assign_change_asset_permission(
                    service_url,
                    asset.id_string,
                    new_users,
                    session,
                )
