"""
RegistrationForm model
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property

from onadata.apps.logger.models import EntityList, XForm, XFormVersion
from onadata.libs.models import AbstractBase


class RegistrationForm(AbstractBase):
    """Form that creates entities in an entity list"""

    entity_list = models.ForeignKey(
        EntityList,
        related_name="registration_forms",
        on_delete=models.CASCADE,
    )
    xform = models.ForeignKey(
        XForm,
        related_name="registration_lists",
        on_delete=models.CASCADE,
        help_text=_("XForm that creates entities"),
    )
    version = models.ForeignKey(
        XFormVersion,
        related_name="registration_forms",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    json = models.JSONField(default=dict)

    class Meta(AbstractBase.Meta):
        unique_together = (
            "entity_list",
            "xform",
        )

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"

    @cached_property
    def save_to(self) -> dict[str, str]:
        """Maps the save_to alias to the original field"""
        result = {}
        fields = self.json.get("children", [])
        entity_properties = filter(
            lambda field: "bind" in field and "entities:saveto" in field["bind"], fields
        )

        for field in entity_properties:
            alias = field["bind"]["entities:saveto"]
            result[alias] = field["name"]

        return result
