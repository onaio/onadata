"""
Entity model
"""
from django.db import models

from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.registration_form import RegistrationForm
from onadata.apps.logger.xform_instance_parser import get_entity_uuid_from_xml
from onadata.libs.models import AbstractBase


class Entity(AbstractBase):
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

    def __str__(self) -> str:
        return f"{self.pk}|{self.registration_form}"

    def save(self, *args, **kwargs) -> None:
        if self.xml:
            self.uuid = get_entity_uuid_from_xml(self.xml)

        super().save(*args, **kwargs)
