"""
Password History Class Module

This module contains the `PasswordHistory` model which is used to track
password changes for a user.
"""
from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_history"
    )
    hashed_password = models.CharField(max_length=128, unique=True, db_index=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}-pass-{self.changed_at}"

    @classmethod
    def user_pre_save(cls, sender, instance=None, created=False, **kwargs):
        if not created and instance.pk:
            current_password = User.objects.get(pk=instance.pk).password
            if current_password != instance.password and current_password:
                cls.objects.create(
                    user=instance, hashed_password=current_password
                )

    class Meta:
        app_label = "main"

models.signals.pre_save.connect(PasswordHistory.user_pre_save, sender=User)
