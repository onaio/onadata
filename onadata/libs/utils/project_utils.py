# -*- coding=utf-8 -*-
"""
project_utils module - apply project permissions to a form.
"""
import sys

from celery import task
from django.conf import settings
from django.db import IntegrityError

from onadata.apps.logger.models import Project, XForm
from onadata.libs.permissions import (ROLES, OwnerRole,
                                      get_object_users_with_permissions)
from onadata.libs.utils.common_tags import OWNER_TEAM_NAME
from onadata.libs.utils.common_tools import report_exception


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
    for perm in get_object_users_with_permissions(
            xform, with_group_users=True):
        user = perm['user']
        role_name = perm['role']
        role = ROLES.get(role_name)
        if role and (user != xform.user and project.user != user and
                     project.created_by != user):
            role.remove_obj_permissions(user, xform)

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


# pylint: disable=invalid-name
@task(bind=True, max_retries=3)
def set_project_perms_to_xform_async(self, xform_id, project_id):
    """
    Apply project permissions for ``project_id`` to a form ``xform_id`` task.
    """
    def _set_project_perms():
        try:
            xform = XForm.objects.get(id=xform_id)
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, XForm.DoesNotExist) as e:
            msg = '%s: Setting project %d permissions to form %d failed.' % (
                type(e), project_id, xform_id)
            # make a report only on the 3rd try.
            if self.request.retries > 2:
                report_exception(msg, e, sys.exc_info())
            self.retry(countdown=60 * self.request.retries, exc=e)
        else:
            set_project_perms_to_xform(xform, project)

    try:
        if getattr(settings, 'SLAVE_DATABASES', []):
            from multidb.pinning import use_master
            with use_master:
                _set_project_perms()
        else:
            _set_project_perms()
    except (Project.DoesNotExist, XForm.DoesNotExist) as e:
        # make a report only on the 3rd try.
        if self.request.retries > 2:
            msg = '%s: Setting project %d permissions to form %d failed.' % (
                type(e), project_id, xform_id)
            report_exception(msg, e, sys.exc_info())
        # let's retry if the record may still not be available in read replica.
        self.retry(countdown=60 * self.request.retries)
    except IntegrityError:
        # Nothing to do, fail silently, permissions seems to have been applied
        # already.
        pass
    except Exception as e:  # pylint: disable=broad-except
        msg = '%s: Setting project %d permissions to form %d failed.' % (
            type(e), project_id, xform_id)
        report_exception(msg, e, sys.exc_info())
