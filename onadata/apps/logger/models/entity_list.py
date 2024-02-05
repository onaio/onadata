"""
EntityList model
"""

from datetime import datetime

from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.project import Project
from onadata.libs.models import AbstractBase
from onadata.libs.utils.cache_tools import (
    ENTITY_LIST_UPDATES,
    ENTITY_LIST_UPDATES_LAST_UPDATE_TIME,
)


class EntityList(AbstractBase):
    """The dataset where each entity will be save to

    Entities of the same type are organized in entity lists
    """

    # Keys for the metadata JSON field
    METADATA_ENTITY_UPDATE_TIME = "last_entity_update_time"
    METADATA_NUM_ENTITIES = "num_entities"

    name = models.CharField(
        max_length=255,
        help_text=_("The name that the follow-up form will reference"),
    )
    project = models.ForeignKey(
        Project,
        related_name="entity_lists",
        on_delete=models.CASCADE,
    )
    metadata = models.JSONField(default=dict)
    exports = GenericRelation("viewer.GenericExport")

    class Meta(AbstractBase.Meta):
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
    def current_last_entity_update_time(self) -> datetime | None:
        """The absolute date and time of the latest Entity to be updated

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
            ).latest("updated_at")
        except ObjectDoesNotExist:
            return None

        return latest_entity.updated_at

    @property
    def cached_last_entity_update_time(self) -> datetime | None:
        """The date and time of the latest Entity to be updated stored in cache

        The data is available in the cache if new Entities have been
        created since the cron job that persists the data in the
        database was last run

        Returns:
            datetime | None: The datetime or None if unvailable
        """
        cached_updates: dict[int, dict] = cache.get(ENTITY_LIST_UPDATES, {})

        if cached_updates.get(self.pk) is None:
            return None

        time_str: str | None = cached_updates[self.pk].get(
            ENTITY_LIST_UPDATES_LAST_UPDATE_TIME
        )

        if time_str is None:
            return None

        try:
            return datetime.fromisoformat(time_str)

        except ValueError:
            return None

    @property
    # pylint: disable=invalid-name
    def persisted_last_entity_update_time(self) -> datetime | None:
        """The date and time of the latest Entity to be updated persisted in DB

        Returns:
            datetime | None: The datetime or None if unvailable
        """
        time_str: str | None = self.metadata.get(EntityList.METADATA_ENTITY_UPDATE_TIME)

        if time_str is None:
            return None

        try:
            return datetime.fromisoformat(time_str)

        except ValueError:
            return None

    @property
    def last_entity_update_time(self) -> datetime | None:
        """The date and time of the latest Entity to be updated

        First checks the cache, if value not found; checks the
        persisted value in database, if value not found;
        queries the database to get the absolute value

        Returns:
            datetime | None: The datetime or None if unvailable
        """
        return (
            self.cached_last_entity_update_time
            or self.persisted_last_entity_update_time
            or self.current_last_entity_update_time
        )

    def get_num_entities(self, force_update=False) -> int:
        """Returns the total number of Entities

        Args:
            force_update (bool): If true, a query will be
            made and the result used to update the data
            in metadata

        Returns:
            int: The number of Entities an EntityList dataset
            has
        """
        if not force_update:
            return self.metadata.get(self.METADATA_NUM_ENTITIES, 0)

        # pylint: disable=invalid-name
        Entity = apps.get_model("logger.entity")
        count = Entity.objects.filter(
            registration_form__entity_list=self, deleted_at__isnull=True
        ).count()
        self.metadata = {**self.metadata, self.METADATA_NUM_ENTITIES: count}
        self.save(update_fields=["metadata", "updated_at"])
        return count
