"""
ProjectInvitation class
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from onadata.apps.logger.models import Project
from onadata.libs.models.base_model import BaseModel


class ProjectInvitation(BaseModel):
    """ProjectInvitation model class"""

    class Meta(BaseModel.Meta):
        app_label = "logger"
        unique_together = (
            "email",
            "project",
            "status",
        )

    class Status(models.IntegerChoices):
        """Choices for `status` field"""

        PENDING = 1, _("Pending")
        ACCEPTED = 2, _("Accepted")
        REVOKED = 3, _("Revoked")

    email = models.EmailField()
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="invitations"
    )
    role = models.CharField(max_length=100)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    resent_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email}|{self.project}"

    def save(self, *args, **kwargs) -> None:
        now = timezone.now()

        if self.status == self.Status.REVOKED and not self.revoked_at:
            self.revoked_at = now

        if self.status == self.Status.ACCEPTED and not self.accepted_at:
            self.accepted_at = now

        return super().save(*args, **kwargs)
