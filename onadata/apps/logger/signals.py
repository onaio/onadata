# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import Entity, Instance, RegistrationForm
from onadata.apps.logger.xform_instance_parser import get_meta_from_xml
from onadata.libs.utils.logger_tools import (
    create_entity as create_new_entity,
    update_entity,
)


# pylint: disable=unused-argument
@receiver(post_save, sender=Instance, dispatch_uid="create_entity")
def create_entity(sender, instance=Instance | None, created=False, **kwargs):
    """Create an Entity if an Instance's form is also RegistrationForm"""
    if created and instance:
        if RegistrationForm.objects.filter(
            xform=instance.xform, is_active=True
        ).exists():
            entity_node = get_meta_from_xml(instance.xml, "entity")
            registration_form = RegistrationForm.objects.filter(
                xform=instance.xform, is_active=True
            ).first()

            if entity_node.getAttribute("create"):
                # Create entity
                create_new_entity(instance, registration_form)

            if entity_node.getAttribute("update"):
                # Update entity
                update_entity(
                    entity_node.getAttribute("id"), instance, registration_form
                )


@receiver(post_save, sender=Entity, dispatch_uid="update_entity_json")
def update_entity_json(sender, instance=Entity | None, created=False, **kwargs):
    """Update and Entity json on creation"""
    if created and instance:
        json = instance.json
        json["id"] = instance.pk
        # Queryset.update ensures the model's save is not called and
        # the pre_save and post_save signals aren't sent
        Entity.objects.filter(pk=instance.pk).update(json=json)
