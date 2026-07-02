"""
Password History Class Module

This module contains the `PasswordHistory` model which is used to track
password changes for a user.
"""

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class PasswordHistory(models.Model):
    """
    Password History Model used to track password changes for a user.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_history"
    )
    hashed_password = models.CharField(max_length=128, db_index=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}-pass-{self.changed_at}"

    @classmethod
    # pylint: disable=unused-argument
    def user_pre_save(cls, sender, instance=None, created=False, **kwargs):  # noqa
        """
        Pre-save signal handler for the `User` model; Used to ensure
        that the `PasswordHistory` is updated when a user changes
        """
        if not created and instance.pk:
            current_password = User.objects.get(pk=instance.pk).password
            if current_password != instance.password and current_password:
                # Record the outgoing hash. Uniqueness is per (user,
                # hashed_password), so re-recording a hash this user already
                # has — e.g. when Django re-hashes/upgrades a stale password on
                # login and re-saves the user — is a no-op rather than an
                # IntegrityError. get_or_create keeps that idempotent without
                # aborting the in-progress User.save().
                cls.objects.get_or_create(
                    user=instance, hashed_password=current_password
                )

    class Meta:
        app_label = "main"
        unique_together = (("user", "hashed_password"),)


models.signals.pre_save.connect(PasswordHistory.user_pre_save, sender=User)
