# -*- coding: utf-8 -*-
"""
logger signals module
"""
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from onadata.apps.logger.models import Entity, EntityList, Instance, SubmissionReview
from onadata.apps.logger.models.xform import clear_project_cache
from onadata.apps.logger.tasks import (
    dec_elist_num_entities_async,
    inc_elist_num_entities_async,
    set_entity_list_perms_async,
)
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.logger_tools import create_or_update_entity_from_instance


# pylint: disable=unused-argument
@receiver(post_save, sender=Instance, dispatch_uid="create_or_update_entity")
def create_or_update_entity(sender, instance, created=False, **kwargs):
    """Create or update an Entity after Instance saved"""
    content_type = ContentType.objects.get_for_model(instance.xform)
    is_review_enabled = MetaData.objects.filter(
        content_type=content_type,
        object_id=instance.xform.id,
        data_type="submission_review",
        data_value="true",
    ).exists()
    should_create_or_update = False

    if not is_review_enabled:
        should_create_or_update = True

    else:
        if not created:
            is_review_approved = SubmissionReview.objects.filter(
                instance_id=instance.id, status=SubmissionReview.APPROVED
            ).exists()
            should_create_or_update = is_review_approved

    if should_create_or_update:
        create_or_update_entity_from_instance(instance)


@receiver(post_save, sender=Entity, dispatch_uid="update_enti_el_inc_num_entities")
def increment_entity_list_num_entities(sender, instance, created=False, **kwargs):
    """Increment EntityList `num_entities`"""
    entity_list = instance.entity_list

    if created:
        transaction.on_commit(
            lambda: inc_elist_num_entities_async.delay(entity_list.pk)
        )


@receiver(post_delete, sender=Entity, dispatch_uid="update_enti_el_dec_num_entities")
def decrement_entity_list_num_entities(sender, instance, **kwargs):
    """Decrement EntityList `num_entities`"""
    transaction.on_commit(
        lambda: dec_elist_num_entities_async.delay(instance.entity_list.pk)
    )


@receiver(post_delete, sender=Entity, dispatch_uid="delete_enti_el_last_update_time")
def update_last_entity_update_time_now(sender, instance, **kwargs):
    """Update EntityList `last_entity_update_time`"""
    entity_list = instance.entity_list
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=entity_list.pk).update(
        last_entity_update_time=timezone.now()
    )


@receiver(post_save, sender=Entity, dispatch_uid="update_enti_el_last_update_time")
def update_last_entity_update_time(sender, instance, **kwargs):
    """Update EntityList `last_entity_update_time`"""
    entity_list = instance.entity_list
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=entity_list.pk).update(
        last_entity_update_time=instance.date_modified
    )


@receiver(post_save, sender=EntityList, dispatch_uid="set_entity_list_perms")
def set_entity_list_perms(sender, instance, created=False, **kwargs):
    """Set project permissions to EntityList"""
    if created:
        transaction.on_commit(lambda: set_entity_list_perms_async.delay(instance.pk))


@receiver(post_delete, sender=EntityList, dispatch_uid="delete_entity_list_metadata")
def delete_entity_list_metadata(sender, instance, **kwargs):
    """Delete EntityList related data on delete"""
    clear_project_cache(instance.project.pk)
    # We get original name incase name has been modified in the case where
    # EntityList was first soft deleted
    entity_list_name = instance.name.split("-")[0]
    MetaData.objects.filter(
        data_type="media",
        data_value=f"entity_list {instance.pk} {entity_list_name}",
    ).delete()
