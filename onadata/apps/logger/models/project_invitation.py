"""
ProjectInvitation class
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from onadata.apps.logger.models.project import Project

User = get_user_model()


# pylint: disable=too-many-ancestors
class ProjectInvitation(models.Model):
    """ProjectInvitation model class"""

    class Meta:
        app_label = "logger"

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
    invited_by = models.ForeignKey(
        User,
        related_name="project_invitations_created",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    accepted_by = models.ForeignKey(
        User,
        related_name="project_invitations_accepted",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    resent_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email}|{self.project}"

    def accept(self, accepted_by=None, accepted_at=None) -> None:
        """Accept invitation"""

        self.accepted_at = accepted_at or timezone.now()
        self.accepted_by = accepted_by
        self.status = ProjectInvitation.Status.ACCEPTED
        self.save()

    def revoke(self, revoked_at=None) -> None:
        """Revoke invitation"""
        self.revoked_at = revoked_at or timezone.now()
        self.status = ProjectInvitation.Status.REVOKED
        self.save()
