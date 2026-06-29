"""
PendingEmailChange model and OTP helpers.

Stores a pending email-address change for a user, protected by a
short-lived 6-digit one-time code.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class PendingEmailChange(models.Model):
    """
    Tracks a pending email-address change for a single user.

    One row per user (OneToOne).  Call ``start()`` to create/replace
    an entry and obtain the raw OTP; call ``verify()`` on the instance
    to validate the code the user submitted.
    """

    TTL_SECONDS = 300
    MAX_ATTEMPTS = 5

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pending_email_change",
    )
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "main"

    def __str__(self):
        return f"PendingEmailChange(user={self.user_id}, new_email={self.new_email})"

    @classmethod
    def start(cls, user, new_email: str):
        """
        Generate a fresh 6-digit OTP, (re-)create the pending-change row,
        and return ``(instance, raw_code)``.

        Any previous pending change for the same user is replaced.
        """
        code = f"{secrets.randbelow(1_000_000):06d}"
        pec, _ = cls.objects.update_or_create(
            user=user,
            defaults={
                "new_email": new_email.strip().lower(),
                "code_hash": _sha256(code),
                "expires_at": timezone.now() + timedelta(seconds=cls.TTL_SECONDS),
                "attempts": 0,
            },
        )
        return pec, code

    def verify(self, raw_code: str) -> bool:
        """
        Validate *raw_code* against the stored hash.

        Returns ``False`` immediately if the record is expired or the
        attempt budget is exhausted.  Always increments ``attempts``
        before comparing (so an exhausted budget is detected on the
        *next* call, not this one — MAX_ATTEMPTS wrong guesses are
        allowed before the correct code is also rejected).
        """
        if timezone.now() >= self.expires_at or self.attempts >= self.MAX_ATTEMPTS:
            return False
        self.attempts = models.F("attempts") + 1
        self.save(update_fields=["attempts"])
        self.refresh_from_db(fields=["attempts"])
        return hmac.compare_digest(self.code_hash, _sha256(raw_code or ""))
