# -*- coding: utf-8 -*-
"""
MergedXForm model - stores info on forms to merge.
"""
from django.db import models, transaction
from django.db.models.signals import post_save

from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import set_uuid


class MergedXForm(XForm):
    """
    Merged XForms
    """

    xforms = models.ManyToManyField("logger.XForm", related_name="mergedxform_ptr")

    class Meta:
        app_label = "logger"

    def save(self, *args, **kwargs):
        set_uuid(self)
        return super().save(*args, **kwargs)


# pylint: disable=unused-argument
def set_object_permissions(sender, instance=None, created=False, **kwargs):
    """Set object permissions when a MergedXForm has been created."""

    if created:
        # pylint: disable=import-outside-toplevel
        from onadata.libs.permissions import OwnerRole

        OwnerRole.add(instance.user, instance)
        OwnerRole.add(instance.user, instance.xform_ptr)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)
            OwnerRole.add(instance.created_by, instance.xform_ptr)

        from onadata.libs.utils.project_utils import (
            set_project_perms_to_xform_async,
        )

        transaction.on_commit(
            lambda: set_project_perms_to_xform_async.delay(
                instance.pk, instance.project.pk
            )
        )


post_save.connect(
    set_object_permissions,
    sender=MergedXForm,
    dispatch_uid="set_project_perms_to_merged_xform",
)
