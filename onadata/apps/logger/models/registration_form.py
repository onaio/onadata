"""
RegistrationForm model
"""
import json

from django.db import models
from django.utils.translation import gettext_lazy as _

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

    class Meta(AbstractBase.Meta):
        unique_together = (
            "entity_list",
            "xform",
        )

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"

    def get_save_to(self, version: str | None = None) -> dict[str, str]:
        """Maps the save_to alias to the original field"""
        if version:
            xform_version = XFormVersion.objects.get(version=version, xform=self.xform)
            xform_json = json.loads(xform_version.json)

        else:
            xform_json = self.xform.json

        result = {}
        fields = xform_json.get("children", [])
        entity_properties = filter(
            lambda field: "bind" in field and "entities:saveto" in field["bind"], fields
        )

        for field in entity_properties:
            alias = field["bind"]["entities:saveto"]
            result[alias] = field["name"]

        return result
