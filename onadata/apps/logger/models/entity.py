"""
Entity model
"""

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
    uuid = models.CharField(max_length=249, default="", db_index=True)
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
            self.entity_list.num_entities = models.F("num_entities") - 1
            self.entity_list.last_entity_update_time = deletion_time
            self.entity_list.save()

    class Meta(BaseModel.Meta):
        app_label = "logger"


class EntityHistory(BaseModel):
    """Maintains a history of Entity updates

    An Entity can be created/updated from a form or via API
    """

    class Meta(BaseModel.Meta):
        app_label = "logger"

    entity = models.ForeignKey(
        Entity,
        related_name="history",
        on_delete=models.CASCADE,
    )
    registration_form = models.ForeignKey(
        RegistrationForm,
        on_delete=models.CASCADE,
        related_name="entity_history",
        null=True,
        blank=True,
    )
    instance = models.ForeignKey(
        Instance,
        on_delete=models.SET_NULL,
        related_name="entity_history",
        null=True,
        blank=True,
    )
    xml = models.TextField(blank=True, null=True)
    json = models.JSONField(default=dict)
    form_version = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
