# -*- coding: utf-8 -*-
"""
A custom ModelBackend class module.
"""
# The onadata import below is ordered per the project's isort config
# (known-first-party=onadata); silence Codacy's stricter pylint import checks.
# pylint: disable=wrong-import-position,ungrouped-imports
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend as DjangoModelBackend

from onadata.libs.permissions import is_organization_user

User = get_user_model()


class ModelBackend(DjangoModelBackend):
    """
    A custom ModelBackend class
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Username is case insensitive. Supports using email in place of username

        Username matches are tried before email matches: ``username`` is unique,
        so a user typing their own username always resolves to their account.
        ``email`` is not unique -- several accounts can share one -- so when the
        supplied value matches by email the candidates are resolved by password
        rather than an arbitrary ``.first()``. This avoids both logging a user
        into the wrong account and rejecting valid credentials that belong to a
        non-first duplicate.
        """
        if username is None or password is None:
            return None

        username_matches = User.objects.filter(username__iexact=username)
        email_matches = User.objects.filter(email__iexact=username)
        # Username is unique, so username matches are tried first; email is not,
        # so email collisions are resolved by password. Candidates are
        # de-duplicated (a value can match both a username and an email) so each
        # account's deliberately-expensive password hash is verified at most
        # once. The work is bounded by the small number of accounts that share
        # the supplied username/email.
        seen_ids = set()
        for user in list(username_matches) + list(email_matches):
            if user.pk in seen_ids:
                continue
            seen_ids.add(user.pk)
            if not user.check_password(password):
                continue
            # Organization accounts are not loginnable human accounts; their
            # User row exists only to hold permissions and ownership. Skip them
            # so an org account can never establish a session -- and never
            # blocks a legitimate human account that shares its email.
            if is_organization_user(user):
                continue
            return user

        return None
