"""
RegistrationForm model
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models import EntityList, XForm
from onadata.libs.models import AbstractBase


class RegistrationForm(AbstractBase):
    """Form that creates entities in an entity list"""

    entity_list = models.ForeignKey(
        EntityList,
        related_name="registration_forms",
        on_delete=models.CASCADE,
    )
    save_to = models.JSONField(
        default=dict,
        help_text=_(
            "Maps the save_to field saved in the XLSForm to the original field"
        ),
    )
    xform = models.ForeignKey(
        XForm,
        related_name="registration_lists",
        on_delete=models.CASCADE,
        help_text=_("XForm that creates entities"),
    )

    def __str__(self):
        return f"{self.xform}|{self.entity_list.name}"
