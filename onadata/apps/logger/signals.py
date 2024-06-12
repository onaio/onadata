# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import Entity, Instance, RegistrationForm
from onadata.apps.logger.xform_instance_parser import get_meta_from_xml
from onadata.libs.utils.logger_tools import (
    create_entity_from_instance,
    update_entity_from_instance,
)


# pylint: disable=unused-argument
@receiver(post_save, sender=Instance, dispatch_uid="create_or_update_entity")
def create_or_update_entity(sender, instance, created=False, **kwargs):
    """Create or update an Entity after Instance saved"""
    if created and instance:
        if RegistrationForm.objects.filter(
            xform=instance.xform, is_active=True
        ).exists():
            entity_node = get_meta_from_xml(instance.xml, "entity")
            registration_form = RegistrationForm.objects.filter(
                xform=instance.xform, is_active=True
            ).first()
            mutation_success_checks = ["1", "true"]
            entity_uuid = entity_node.getAttribute("id")

            if (
                entity_node.getAttribute("update") in mutation_success_checks
                and entity_uuid is not None
                and Entity.objects.filter(uuid=entity_uuid).exists()
            ):
                # Update Entity
                update_entity_from_instance(entity_uuid, instance, registration_form)

            elif entity_node.getAttribute("create") in mutation_success_checks:
                # Create Entity
                create_entity_from_instance(instance, registration_form)


@receiver(post_save, sender=Entity, dispatch_uid="add_entity_json_id")
def add_entity_json_id(sender, instance, created=False, **kwargs):
    """Add id to Entity json after Entity created"""
    if not instance:
        return

    if created:
        json = instance.json
        json["id"] = instance.pk
        # Queryset.update ensures the model's save is not called and
        # the pre_save and post_save signals aren't sent
        Entity.objects.filter(pk=instance.pk).update(json=json)


@receiver(post_save, sender=Entity, dispatch_uid="update_entity_dataset")
def update_entity_dataset(sender, instance, created=False, **kwargs):
    """Update EntityList when Entity is created or updated"""
    if not instance:
        return

    entity_list = instance.entity_list

    if created:
        entity_list.num_entities = F("num_entities") + 1

    entity_list.last_entity_update_time = instance.date_modified
    entity_list.save()
