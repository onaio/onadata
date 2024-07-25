"""
FollowUpForm model
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.xform import XForm
from onadata.libs.models import BaseModel


class FollowUpForm(BaseModel):
    """Forms that consumes entities from an entity list

    No changes are made to any entities
    """

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = (
            "entity_list",
            "xform",
        )

    entity_list = models.ForeignKey(
        EntityList,
        related_name="follow_up_forms",
        on_delete=models.CASCADE,
    )
    xform = models.ForeignKey(
        XForm,
        related_name="follow_up_forms",
        on_delete=models.CASCADE,
        help_text=_("XForm that consumes entities"),
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"
