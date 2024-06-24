# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.logger.models import Entity, EntityList, Instance, RegistrationForm
from onadata.apps.logger.xform_instance_parser import get_meta_from_xml
from onadata.apps.logger.tasks import set_entity_list_perms_async
from onadata.libs.utils.logger_tools import (
    create_entity_from_instance,
    update_entity_from_instance,
)


# pylint: disable=unused-argument
@receiver(post_save, sender=Instance, dispatch_uid="create_or_update_entity")
def create_or_update_entity(sender, instance, created=False, **kwargs):
    """Create or update an Entity after Instance saved"""
    if instance:
        if RegistrationForm.objects.filter(
            xform=instance.xform, is_active=True
        ).exists():
            entity_node = get_meta_from_xml(instance.xml, "entity")
            registration_form = RegistrationForm.objects.filter(
                xform=instance.xform, is_active=True
            ).first()
            mutation_success_checks = ["1", "true"]
            entity_uuid = entity_node.getAttribute("id")
            exists = False

            if entity_uuid is not None:
                exists = Entity.objects.filter(uuid=entity_uuid).exists()

            if exists and entity_node.getAttribute("update") in mutation_success_checks:
                # Update Entity
                update_entity_from_instance(entity_uuid, instance, registration_form)

            elif (
                not exists
                and entity_node.getAttribute("create") in mutation_success_checks
            ):
                # Create Entity
                create_entity_from_instance(instance, registration_form)


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


@receiver(post_save, sender=EntityList, dispatch_uid="set_entity_list_perms")
def set_entity_list_perms(sender, instance, created=False, **kwargs):
    """Set project permissions to EntityList"""
    if created:
        transaction.on_commit(lambda: set_entity_list_perms_async.delay(instance.pk))
