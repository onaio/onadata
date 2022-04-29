# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import MergedXForm
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.xform import clear_project_cache
from onadata.libs.permissions import OwnerRole
from onadata.libs.utils.cache_tools import (
    IS_ORG,
    safe_delete,
)
from onadata.libs.utils.project_utils import set_project_perms_to_xform


# pylint: disable=unused-argument
@receiver(
    post_save, sender=MergedXForm, dispatch_uid="set_project_perms_to_merged_xform"
)
def set_project_object_permissions(sender, instance=None, created=False, **kwargs):
    """Apply project permission to the merged form."""
    if created:
        OwnerRole.add(instance.user, instance)
        OwnerRole.add(instance.user, instance.xform_ptr)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)
            OwnerRole.add(instance.created_by, instance.xform_ptr)

        set_project_perms_to_xform(instance, instance.project)
        set_project_perms_to_xform(instance.xform_ptr, instance.project)


# pylint: disable=unused-argument
def set_xform_object_permissions(sender, instance=None, created=False, **kwargs):
    """Apply project permissions to the user that created the form."""
    # clear cache
    project = instance.project
    project.refresh_from_db()
    clear_project_cache(project.pk)
    safe_delete(f"{IS_ORG}{instance.pk}")

    if created:
        OwnerRole.add(instance.user, instance)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)

        set_project_perms_to_xform(instance, project)


post_save.connect(
    set_xform_object_permissions, sender=XForm, dispatch_uid="xform_object_permissions"
)
