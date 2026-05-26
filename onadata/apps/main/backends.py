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
        for user in list(username_matches) + list(email_matches):
            if user.check_password(password):
                # Organization accounts are not loginnable human accounts; their
                # User row exists only to hold permissions and ownership. Refuse
                # authentication so an org account can never establish a session.
                if is_organization_user(user):
                    return None
                return user

        return None
