"""
Entity model
"""

from django.contrib.auth import get_user_model
from django.db import models

from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.registration_form import RegistrationForm
from onadata.apps.logger.xform_instance_parser import get_entity_uuid_from_xml
from onadata.libs.models import BaseModel

User = get_user_model()


class Entity(BaseModel):
    """An entity created by a registration form"""

    registration_form = models.ForeignKey(
        RegistrationForm,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    instance = models.OneToOneField(
        Instance,
        on_delete=models.SET_NULL,
        related_name="entity",
        null=True,
        blank=True,
    )
    xml = models.TextField()
    json = models.JSONField(default=dict)
    version = models.CharField(max_length=255, null=True)
    uuid = models.CharField(max_length=249, default="", db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User, related_name="deleted_entities", null=True, on_delete=models.SET_NULL
    )

    def __str__(self) -> str:
        return f"{self.pk}|{self.registration_form}"

    def save(self, *args, **kwargs) -> None:
        if self.xml:
            self.uuid = get_entity_uuid_from_xml(self.xml)

        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        app_label = "logger"
