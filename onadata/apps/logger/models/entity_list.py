"""
EntityList model
"""

from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.project import Project
from onadata.libs.models import BaseModel


class EntityList(BaseModel):
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
    num_entities = models.IntegerField(default=0)
    last_entity_update_time = models.DateTimeField(blank=True, null=True)
    exports = GenericRelation("viewer.GenericExport")

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = (
            "name",
            "project",
        )

    def __str__(self):
        return f"{self.name}|{self.project}"

    @property
    def properties(self) -> list[str]:
        """All dataset properties

        Multiple forms can define matching or different properties for the same
        dataset

        Returns:
            list: properties defined by all forms creating Entities for
            the dataset
        """
        registration_forms_qs = self.registration_forms.filter(is_active=True)
        dataset_properties = set()

        for form in registration_forms_qs:
            form_properties = set(form.get_save_to().keys())
            dataset_properties.update(form_properties)

        return list(dataset_properties)

    @property
    def queried_last_entity_update_time(self) -> datetime | None:
        """The datetime of the latest Entity to be updated queried from DB

        This value is queried from the database. It could be a
        serious performance problem if the record set is large.

        Returns:
            datetime | None: The datetime or None if no Entities are unvailable
        """
        # pylint: disable=invalid-name
        Entity = apps.get_model("logger.entity")  # noqa

        try:
            latest_entity = Entity.objects.filter(
                registration_form__entity_list=self
            ).latest("date_modified")
        except ObjectDoesNotExist:
            return None

        return latest_entity.date_modified

    @property
    def queried_num_entities(self) -> int:
        """The total number of Entities queried from the database

        Returns:
            int: The Entity count
        """
        # pylint: disable=invalid-name
        Entity = apps.get_model("logger.entity")  # noqa

        return Entity.objects.filter(
            registration_form__entity_list=self, deleted_at__isnull=True
        ).count()
