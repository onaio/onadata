"""
Entity model
"""

import uuid
import importlib

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone

from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.registration_form import RegistrationForm
from onadata.libs.models import BaseModel

User = get_user_model()


class Entity(BaseModel):
    """An entity created by a registration form"""

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
            self.save(update_fields=["deleted_at", "deleted_by"])
            # Avoid cyclic dependency errors
            logger_tasks = importlib.import_module("onadata.apps.logger.tasks")
            transaction.on_commit(
                lambda: logger_tasks.dec_elist_num_entities_async.delay(
                    self.entity_list.pk
                )
            )

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


class EntityHistory(BaseModel):
    """Maintains a history of Entity updates

    An Entity can be created/updated from a form or via API
    """

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
