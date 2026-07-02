"""
Password History Class Module

This module contains the `PasswordHistory` model which is used to track
password changes for a user.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction


User = get_user_model()


class PasswordHistory(models.Model):
    """
    Password History Model used to track password changes for a user.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_history"
    )
    hashed_password = models.CharField(max_length=128, unique=True, db_index=True)
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
                # ``hashed_password`` is globally unique, so recording an
                # already-stored hash raises IntegrityError. That happens
                # whenever Django re-hashes/upgrades a stale password on login
                # and re-saves the user: the previous hash is re-recorded. An
                # unguarded create() would abort the whole User.save(), the
                # upgraded hash would never persist, and every subsequent login
                # would repeat the failure — a permanent lockout. Swallow the
                # duplicate inside a savepoint so it never breaks the user save.
                try:
                    with transaction.atomic():
                        cls.objects.create(
                            user=instance, hashed_password=current_password
                        )
                except IntegrityError:
                    # Duplicate hash already on record — the expected case
                    # described above. Nothing to store; return so the
                    # in-progress User.save() completes normally.
                    return

    class Meta:
        app_label = "main"


models.signals.pre_save.connect(PasswordHistory.user_pre_save, sender=User)
