"""
Entity model
"""
from django.db import models

from onadata.apps.logger.models import RegistrationForm
from onadata.libs.models import AbstractBase


class Entity(AbstractBase):
    """An entity created by a registration form"""

    registration_form = models.ForeignKey(
        RegistrationForm,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    json = models.JSONField(default=dict)
    version = models.CharField(max_length=255, null=True)

    def __str__(self) -> str:
        return f"{self.pk}|{self.registration_form}"
