# -*- coding: utf-8 -*-
"""
A custom ModelBackend class module.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend as DjangoModelBackend
from django.db.models import Q

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
            return user

        return None
