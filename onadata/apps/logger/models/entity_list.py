"""
EntityList model
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


from guardian.models import UserObjectPermissionBase, GroupObjectPermissionBase
from guardian.compat import user_model_label

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import clear_project_cache
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.models import BaseModel
from onadata.libs.utils.model_tools import queryset_iterator

User = get_user_model()


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
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

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

    @transaction.atomic()
    def soft_delete(self, deleted_by=None):
        """Soft delete EntityList"""
        if self.deleted_at is None:
            deletion_time = timezone.now()
            deletion_suffix = deletion_time.strftime("-deleted-at-%s")
            self.deleted_at = deletion_time
            self.deleted_by = deleted_by
            original_name = self.name
            self.name += deletion_suffix
            self.name = self.name[:255]  # Only first 255 characters
            self.save()
            clear_project_cache(self.project.pk)
            # Soft deleted follow up forms MetaData
            metadata_qs = MetaData.objects.filter(
                data_type="media",
                data_value=f"entity_list {self.pk} {original_name}",
            )

            for datum in queryset_iterator(metadata_qs):
                datum.soft_delete()

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = (
            "name",
            "project",
        )
        indexes = [models.Index(fields=["deleted_at"])]


class EntityListUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(
        EntityList, on_delete=models.CASCADE, db_index=False
    )
    # Override fields' (db_index=False) so that we can create indexes manually
    # concurrently in the migration
    # (0018_entityhistory_entitylistgroupobjectpermission_and_more) for
    # improved performance in huge databases
    user = models.ForeignKey(user_model_label, on_delete=models.CASCADE, db_index=False)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, db_index=False)


# pylint: disable=too-few-public-methods
class EntityListGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(
        EntityList, on_delete=models.CASCADE, db_index=False
    )
    # Override fields' (db_index=False) so that we can create indexes manually
    # concurrently in the migration
    # (0018_entityhistory_entitylistgroupobjectpermission_and_more) for
    # improved performance in huge databases
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_index=False)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, db_index=False)
