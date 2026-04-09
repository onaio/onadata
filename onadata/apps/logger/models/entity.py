"""
Entity model
"""

import importlib
import uuid

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.registration_form import RegistrationForm
from onadata.libs.models import BaseModel

User = get_user_model()


class Entity(BaseModel):
    """A Entity created by a RegistrationForm"""

    entity_list = models.ForeignKey(
        EntityList,
        related_name="entities",
        on_delete=models.CASCADE,
    )
    json = models.JSONField(default=dict)
    uuid = models.UUIDField(default=uuid.uuid4, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    def __str__(self) -> str:
        return f"{self.pk}|{self.entity_list}"

    @transaction.atomic()
    def soft_delete(self, deleted_by=None):
        """Soft delete Entity"""
        if self.deleted_at is None:
            deletion_time = timezone.now()
            self.deleted_at = deletion_time
            self.deleted_by = deleted_by
            self.save(update_fields=["deleted_at", "deleted_by", "date_modified"])

    class Meta(BaseModel.Meta):
        app_label = "logger"
        indexes = [
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["entity_list", "uuid"]),
        ]
        unique_together = (
            "entity_list",
            "uuid",
        )


# pylint: disable=too-many-ancestors
class EntityHistory(BaseModel):
    """Maintains a history of Entity updates

    An Entity can be created/updated from a form or via API
    """

    class MutationType(models.TextChoices):
        """Choices for mutation type"""

        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")

    class Meta(BaseModel.Meta):
        app_label = "logger"

    # Set db_index=False so that we can create indexes manually concurrently in the
    # migration (0018_entityhistory_entitylistgroupobjectpermission_and_more) for
    # improved performance in huge databases
    entity = models.ForeignKey(
        Entity,
        related_name="history",
        on_delete=models.CASCADE,
        db_index=False,
    )
    registration_form = models.ForeignKey(
        RegistrationForm,
        on_delete=models.CASCADE,
        related_name="entity_history",
        null=True,
        blank=True,
        db_index=False,
    )
    instance = models.ForeignKey(
        Instance,
        on_delete=models.SET_NULL,
        related_name="entity_history",
        null=True,
        blank=True,
        db_index=False,
    )
    xml = models.TextField(blank=True, null=True)
    json = models.JSONField(default=dict)
    form_version = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, db_index=False
    )
    mutation_type = models.CharField(
        max_length=20,
        choices=MutationType.choices,
        default=MutationType.CREATE,
    )


# pylint: disable=unused-argument
def incr_entity_list_num_entities(sender, instance, created=False, **kwargs):
    """Increment EntityList `num_entities`"""
    # Avoid cyclic dependency errors
    logger_tasks = importlib.import_module("onadata.apps.logger.tasks")
    entity_list = instance.entity_list

    if created:
        transaction.on_commit(
            lambda: logger_tasks.adjust_elist_num_entities_async.delay(
                entity_list.pk, delta=1
            )
        )


def decr_entity_list_num_entities_on_hard_delete(sender, instance, **kwargs):
    """Decrement EntityList `num_entities`"""
    # Avoid cyclic dependency errors
    logger_tasks = importlib.import_module("onadata.apps.logger.tasks")
    transaction.on_commit(
        lambda: logger_tasks.adjust_elist_num_entities_async.delay(
            instance.entity_list.pk, delta=-1
        )
    )


def decr_entity_list_num_entities_on_soft_delete(sender, instance, **kwargs):
    """Decrement EntityList `num_entities` on Entity soft delete"""
    if not instance.pk or instance.deleted_at is None:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.deleted_at is None and instance.deleted_at is not None:
        # Entity was soft deleted
        # Avoid cyclic dependency errors
        logger_tasks = importlib.import_module("onadata.apps.logger.tasks")
        transaction.on_commit(
            lambda: logger_tasks.adjust_elist_num_entities_async.delay(
                instance.entity_list.pk, delta=-1
            )
        )


def update_last_entity_update_time_now(sender, instance, **kwargs):
    """Update EntityList `last_entity_update_time`"""
    entity_list = instance.entity_list
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=entity_list.pk).update(
        last_entity_update_time=timezone.now()
    )


def update_last_entity_update_time(sender, instance, **kwargs):
    """Update EntityList `last_entity_update_time`"""
    entity_list = instance.entity_list
    # Using Queryset.update ensures we do not call the model's save method and
    # signals
    EntityList.objects.filter(pk=entity_list.pk).update(
        last_entity_update_time=instance.date_modified
    )


post_save.connect(
    incr_entity_list_num_entities,
    sender=Entity,
    dispatch_uid="incr_entity_list_num_entities",
)

post_delete.connect(
    decr_entity_list_num_entities_on_hard_delete,
    sender=Entity,
    dispatch_uid="decr_entity_list_num_entities_on_hard_delete",
)

pre_save.connect(
    decr_entity_list_num_entities_on_soft_delete,
    sender=Entity,
    dispatch_uid="decr_entity_list_num_entities_on_soft_delete",
)

post_delete.connect(
    update_last_entity_update_time_now,
    sender=Entity,
    dispatch_uid="delete_enti_el_last_update_time",
)

post_save.connect(
    update_last_entity_update_time,
    sender=Entity,
    dispatch_uid="update_enti_el_last_update_time",
)
