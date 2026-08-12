# -*- coding: utf-8 -*-
"""
Email *identity* helpers — normalization and uniqueness of a user's email.

Single source of truth for the "how is an email canonicalized and is it
already taken" invariant. Kept separate from ``email.py`` (which is about
*delivering* messages) so the responsibility reads from the module name: the
profile serializer and the email-change flow both resolve through here instead
of each re-implementing the ``email__iexact`` + ``exclude(self)`` query.
"""

from django.contrib.auth import get_user_model


def normalize_email(value):
    """Canonical form used everywhere an email is stored or compared."""
    return (value or "").strip().lower()


def email_in_use(email, exclude_user=None):
    """Whether *email* already belongs to a user (case-insensitive)."""
    user_model = get_user_model()
    queryset = user_model.objects.filter(email__iexact=normalize_email(email))
    if exclude_user is not None:
        queryset = queryset.exclude(pk=exclude_user.pk)
    return queryset.exists()
