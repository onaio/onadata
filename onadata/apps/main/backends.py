# -*- coding: utf-8 -*-
"""
A custom ModelBackend class module.
"""
# The onadata import below is ordered per the project's isort config.
# pylint: disable=wrong-import-position,ungrouped-imports
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend as DjangoModelBackend
from django.db.models import Q

from onadata.libs.permissions import is_organization_user

User = get_user_model()


class ModelBackend(DjangoModelBackend):
    """
    A custom ModelBackend class
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Username is case insensitive. Supports using email in place of username
        """
        if username is None or password is None:
            return None

        user = User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ).first()

        if user and user.check_password(password):
            # Organization accounts are not loginnable human accounts; their
            # User row exists only to hold permissions and ownership. Refuse
            # authentication so an org account can never establish a session.
            if is_organization_user(user):
                return None
            return user

        return None
