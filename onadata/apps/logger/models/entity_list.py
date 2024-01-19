"""
EntityList model
"""

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

    class Meta(AbstractBase.Meta):
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
