# -*- coding: utf-8 -*-
"""System checks for the API app."""

from django.conf import settings
from django.core.checks import Error, Tags, register

from cryptography.fernet import Fernet


@register(Tags.security)
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


@register(Tags.security)
# pylint: disable=unused-argument
def two_factor_support_email_check(app_configs, **kwargs):
    """Refuse to start when two-factor is on but SUPPORT_EMAIL is unset.

    The notification emails address the owner to SUPPORT_EMAIL; without it
    ``get_two_factor_email_data`` raises, which a repeated-failure alert would
    turn into a request-time 500. Surface it as a startup error instead.
    """
    if not getattr(settings, "ENABLE_TWO_FACTOR", False):
        return []
    if not getattr(settings, "SUPPORT_EMAIL", ""):
        return [
            Error(
                "ENABLE_TWO_FACTOR is on but SUPPORT_EMAIL is unset.",
                hint="Set SUPPORT_EMAIL to the address the two-factor "
                "notification emails should point account owners to.",
                id="api.E003",
            )
        ]
    return []


@register(Tags.security)
# pylint: disable=unused-argument
def two_factor_secret_key_check(app_configs, **kwargs):
    """Refuse to start when two-factor is on but SECRET_KEY is the default.

    The remember-device cookie is signed with SECRET_KEY; the shipped default
    is public, so leaving it in place lets anyone forge a cookie that skips the
    second factor.
    """
    if not getattr(settings, "ENABLE_TWO_FACTOR", False):
        return []
    insecure_default = getattr(settings, "INSECURE_DEFAULT_SECRET_KEY", None)
    if insecure_default and settings.SECRET_KEY == insecure_default:
        return [
            Error(
                "ENABLE_TWO_FACTOR is on but SECRET_KEY is the shipped default.",
                hint="Override SECRET_KEY (e.g. from the environment); the "
                "remember-device cookie is signed with it.",
                id="api.E004",
            )
        ]
    return []
