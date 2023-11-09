"""
FollowUpForm model
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models import EntityList, XForm
from onadata.libs.models import AbstractBase


class FollowUpForm(AbstractBase):
    """Forms that consumes entities from an entity list

    No changes are made to any entities
    """

    entity_list = models.ForeignKey(
        EntityList,
        related_name="follow_up_forms",
        on_delete=models.CASCADE,
    )
    xform = models.ForeignKey(
        XForm,
        related_name="follow_up_lists",
        on_delete=models.CASCADE,
        help_text=_("XForm that consumes entities"),
    )

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"
