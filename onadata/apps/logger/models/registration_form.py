"""
RegistrationForm model
"""

import json

from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.entity_list import EntityList, EntityListProperty
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
        """Maps the save_to values to the xpaths of their fields

        :param version: XForm version (optional, defaults to current version)
        :type version: str
        :return: save_to values mapped to the xpaths of their fields
        :rtype: dict
        """
        if version:
            xform_version = XFormVersion.objects.get(version=version, xform=self.xform)
            xform_json = json.loads(xform_version.json)

        else:
            xform_json = self.xform.json

        result = {}
        children = xform_json.get("children", [])
        dataset = self.entity_list.name

        def get_entity_dataset(entity_field):
            parameters = entity_field.get("parameters")

            if parameters:
                return parameters.get("dataset")

            for field in entity_field.get("children", []):
                if field.get("name") == "dataset":
                    return field.get("value")

            return None

        def get_container_dataset(form_fields):
            for field in form_fields:
                if field.get("name") == "meta":
                    for meta_field in field.get("children", []):
                        if meta_field.get("name") == "entity":
                            return get_entity_dataset(meta_field)

            return None

        def find_container_fields(form_fields, xpath_prefix=""):
            if get_container_dataset(form_fields) == dataset:
                return form_fields, xpath_prefix

            for field in form_fields:
                if field.get("children", []):
                    found = find_container_fields(
                        field["children"], f"{xpath_prefix}{field['name']}/"
                    )

                    if found is not None:
                        return found

            return None

        def get_entity_property_fields(form_fields, xpath_prefix):
            for field in form_fields:
                if "bind" in field and "entities:saveto" in field["bind"]:
                    alias = field["bind"]["entities:saveto"]
                    result[alias] = f"{xpath_prefix}{field['name']}"

                elif field.get("children", []):
                    child_dataset = get_container_dataset(field["children"])

                    if child_dataset is None or child_dataset == dataset:
                        get_entity_property_fields(
                            field["children"], f"{xpath_prefix}{field['name']}/"
                        )

        container = find_container_fields(children)

        if container is not None:
            container_fields, xpath_prefix = container
            get_entity_property_fields(container_fields, xpath_prefix)

        return result

    @property
    def properties(self) -> list[str]:
        """All EntityList properties the form contributes to"""
        return list(self.get_save_to().keys())


# pylint: disable=unused-argument
def create_elist_properties(sender, instance, **kwargs):
    """Create EntityListProperty from RegistrationForm"""
    for prop in instance.properties:
        if not EntityListProperty.objects.filter(
            name__iexact=prop, entity_list=instance.entity_list
        ).exists():
            EntityListProperty.objects.create(
                name=prop,
                entity_list=instance.entity_list,
                created_by=instance.xform.created_by,
            )


post_save.connect(
    create_elist_properties,
    sender=RegistrationForm,
    dispatch_uid="create_elist_properties",
)
