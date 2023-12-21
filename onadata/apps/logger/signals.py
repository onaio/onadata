# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import Instance, Entity, RegistrationForm


# pylint: disable=unused-argument
@receiver(post_save, sender=Instance, dispatch_uid="create_entity")
def create_entity(sender, instance=Instance | None, created=False, **kwargs):
    """Create an Entity if an Instance's form is also RegistrationForm"""
    if created and instance:
        if RegistrationForm.objects.filter(
            xform=instance.xform, is_active=True
        ).exists():
            registration_form = RegistrationForm.objects.filter(
                xform=instance.xform, is_active=True
            ).first()
            Entity.objects.create(
                registration_form=registration_form,
                xml=instance.xml,
                json=instance.get_dict(),
            )
