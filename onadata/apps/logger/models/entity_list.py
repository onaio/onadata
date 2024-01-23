"""
EntityList model
"""
from datetime import datetime

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.functional import cached_property

from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.project import Project
from onadata.libs.models import AbstractBase


class EntityList(AbstractBase):
    """The dataset where each entity will be save to

    Entities of the same type are organized in entity lists
    """

    name = models.CharField(
        max_length=255,
        help_text=_("The name that the follow-up form will reference"),
    )
    project = models.ForeignKey(
        Project,
        related_name="entity_lists",
        on_delete=models.CASCADE,
    )
    exports = GenericRelation("viewer.GenericExport")

    class Meta(AbstractBase.Meta):
        app_label = "logger"
        unique_together = (
            "name",
            "project",
        )

    def __str__(self):
        return f"{self.name}|{self.project}"

    @cached_property
    def properties(self) -> list[str]:
        """All dataset properties

        Multiple forms can define matching or different properties for the same
        dataset
        """
        registration_forms_qs = self.registration_forms.filter(is_active=True)
        dataset_properties = set()

        for form in registration_forms_qs:
            form_properties = set(form.get_save_to().keys())
            dataset_properties.update(form_properties)

        return list(dataset_properties)

    @cached_property
    def last_entity_creation_time(self) -> datetime | None:
        """The date and time the latest Entity was created"""
        from onadata.apps.logger.models.entity import Entity

        try:
            latest_entity = Entity.objects.filter(
                registration_form__entity_list=self
            ).latest("created_at")

        except ObjectDoesNotExist:
            return None

        return latest_entity.created_at

    @cached_property
    def last_entity_update_time(self) -> datetime | None:
        """The date and time of the latest Entity to be updated"""
        from onadata.apps.logger.models.entity import Entity

        try:
            latest_entity = Entity.objects.filter(
                registration_form__entity_list=self
            ).latest("updated_at")
        except ObjectDoesNotExist:
            return None

        return latest_entity.updated_at
