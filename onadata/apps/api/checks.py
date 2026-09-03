# -*- coding: utf-8 -*-
"""System checks for the API app."""

from django.conf import settings
from django.core.checks import Error, register

from cryptography.fernet import Fernet


@register()
# app_configs is part of the signature Django calls this check with.
# pylint: disable=unused-argument
def two_factor_encryption_keys_check(app_configs, **kwargs):
    """Refuse to start when two-factor is on but its keys are unusable.

    ``ENABLE_TWO_FACTOR`` and ``TWO_FACTOR_FIELD_ENCRYPTION_KEYS`` are set
    independently; with no valid key every enrolment and login would raise at
    runtime, so surface it as a startup error instead of a first-request 500.
    """
    if not getattr(settings, "ENABLE_TWO_FACTOR", False):
        return []
    keys = getattr(settings, "TWO_FACTOR_FIELD_ENCRYPTION_KEYS", None) or []
    if not keys:
        return [
            Error(
                "ENABLE_TWO_FACTOR is on but TWO_FACTOR_FIELD_ENCRYPTION_KEYS "
                "is empty.",
                hint="Set at least one Fernet key so the authenticator seed "
                "and recovery codes can be encrypted at rest.",
                id="api.E001",
            )
        ]
    errors = []
    for key in keys:
        try:
            Fernet(key)
        except (ValueError, TypeError):
            errors.append(
                Error(
                    "A TWO_FACTOR_FIELD_ENCRYPTION_KEYS entry is not a valid "
                    "Fernet key.",
                    hint="Each key must be a url-safe base64-encoded 32-byte "
                    "value, e.g. from Fernet.generate_key().",
                    id="api.E002",
                )
            )
    return errors
