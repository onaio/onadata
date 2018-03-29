from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext as _

from onadata.apps.logger.models.xform import XForm


class MergedXForm(XForm):
    """
    Merged XForms
    """

    xforms = models.ManyToManyField(
        'logger.XForm', related_name='mergedxform_ptr')

    class Meta:
        app_label = 'logger'
        permissions = (("view_mergedxform", _("Can view associated data")), )


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        from onadata.libs.permissions import OwnerRole
        OwnerRole.add(instance.user, instance)
        OwnerRole.add(instance.user, instance.xform_ptr)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)
            OwnerRole.add(instance.created_by, instance.xform_ptr)

        from onadata.libs.utils.project_utils import set_project_perms_to_xform
        set_project_perms_to_xform(instance, instance.project)
        set_project_perms_to_xform(instance.xform_ptr, instance.project)


post_save.connect(
    set_object_permissions,
    sender=MergedXForm,
    dispatch_uid='set_project_perms_to_merged_xform')
