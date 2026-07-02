"""
PendingEmailChange model and OTP helpers.

Stores a pending email-address change for a user, protected by a
short-lived numeric one-time code. Policy knobs (TTL, attempt budget,
code length) are read from settings so deployments can tune them from one
place; the model and the notification email both derive from these values.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Deployment-tunable OTP policy — single source of truth (see email.py, which
# derives the notification's stated expiry from OTP_TTL_SECONDS).
OTP_TTL_SECONDS = getattr(settings, "EMAIL_CHANGE_OTP_TTL_SECONDS", 300)
OTP_MAX_ATTEMPTS = getattr(settings, "EMAIL_CHANGE_OTP_MAX_ATTEMPTS", 5)
OTP_CODE_DIGITS = getattr(settings, "EMAIL_CHANGE_OTP_CODE_DIGITS", 6)


def _hash_code(code: str) -> str:
    """Keyed HMAC-SHA256 of *code* over ``SECRET_KEY``.

    A bare SHA-256 of a short numeric code is trivially reversible from a DB
    read (the keyspace is tiny). Keying with the server secret means a leaked
    ``code_hash`` cannot be brute-forced into a live code without the key.
    """
    return hmac.new(
        settings.SECRET_KEY.encode(), (code or "").encode(), hashlib.sha256
    ).hexdigest()


class PendingEmailChange(models.Model):
    """
    Tracks a pending email-address change for a single user.

    One row per user (OneToOne).  Call ``start()`` to create/replace
    an entry and obtain the raw OTP; call ``consume()`` on the instance
    to validate the submitted code and (on success) atomically retire it.
    """

    # Kept as class attributes for readability/back-compat; sourced from
    # settings so all OTP policy lives in one place.
    TTL_SECONDS = OTP_TTL_SECONDS
    MAX_ATTEMPTS = OTP_MAX_ATTEMPTS
    CODE_DIGITS = OTP_CODE_DIGITS

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
        Generate a fresh OTP, (re-)create the pending-change row, and return
        ``(instance, raw_code)``.

        Any previous pending change for the same user is replaced.
        """
        code = f"{secrets.randbelow(10 ** cls.CODE_DIGITS):0{cls.CODE_DIGITS}d}"
        pec, _ = cls.objects.update_or_create(
            user=user,
            defaults={
                "new_email": new_email.strip().lower(),
                "code_hash": _hash_code(code),
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
        return hmac.compare_digest(self.code_hash, _hash_code(raw_code))

    def consume(self, raw_code: str):
        """
        Verify *raw_code* and, on success, retire the row (single use).

        Returns the pending ``new_email`` when the code is valid, otherwise
        ``None``. Keeping verify-then-delete here means the one-time
        semantics live in one place instead of being split across callers.
        """
        if self.verify(raw_code):
            new_email = self.new_email
            self.delete()
            return new_email
        return None
