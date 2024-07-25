"""
RegistrationForm model
"""

import json

from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.xform_version import XFormVersion
from onadata.libs.models import BaseModel


class RegistrationForm(BaseModel):
    """Form that creates entities in an entity list"""

    entity_list = models.ForeignKey(
        EntityList,
        related_name="registration_forms",
        on_delete=models.CASCADE,
    )
    xform = models.ForeignKey(
        XForm,
        related_name="registration_forms",
        on_delete=models.CASCADE,
        help_text=_("XForm that creates entities"),
    )
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = (
            "entity_list",
            "xform",
        )

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"

    def get_save_to(self, version: str | None = None) -> dict[str, str]:
        """Maps the save_to alias to the original field

        Args:
            version (str | None): XFormVersion's version to use to get properties

        Returns:
            dict: properties used to create entities mapped to their
            original names
        """
        if version:
            xform_version = XFormVersion.objects.get(version=version, xform=self.xform)
            xform_json = json.loads(xform_version.json)

        else:
            xform_json = self.xform.json

        result = {}
        children = xform_json.get("children", [])

        def get_entity_property_fields(form_fields):
            property_fields = []

            for field in form_fields:
                if "bind" in field and "entities:saveto" in field["bind"]:
                    property_fields.append(field)
                elif field.get("children", []):
                    property_fields += get_entity_property_fields(field["children"])

            return property_fields

        for field in get_entity_property_fields(children):
            alias = field["bind"]["entities:saveto"]
            result[alias] = field["name"]

        return result
