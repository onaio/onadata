"""
EntityList model
"""

from django.db import models

from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models import Project
from onadata.libs.models import AbstractBase


class EntityList(AbstractBase):
    """The dataset where each entity will be save to

    Entities of the same type are organized in entity lists
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("The name that the follow-up form will reference"),
    )
    project = models.ForeignKey(
        Project,
        related_name="entity_lists",
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"{self.name}|{self.project}"
