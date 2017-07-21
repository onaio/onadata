from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import MergedXForm
from onadata.libs.permissions import OwnerRole
from onadata.libs.utils.project_utils import set_project_perms_to_xform


@receiver(
    post_save,
    sender=MergedXForm,
    dispatch_uid='set_project_perms_to_merged_xform')
def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        OwnerRole.add(instance.user, instance)
        OwnerRole.add(instance.user, instance.xform_ptr)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)
            OwnerRole.add(instance.created_by, instance.xform_ptr)

        set_project_perms_to_xform(instance, instance.project)
        set_project_perms_to_xform(instance.xform_ptr, instance.project)
