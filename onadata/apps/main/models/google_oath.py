# -*- coding: utf-8 -*-
"""
Google auth token storage model class
"""
from django.conf import settings
from django.db import models
from oauth2client.contrib.django_util.models import CredentialsField

User = settings.AUTH_USER_MODEL    # pylint: disable=C0103


class TokenStorageModel(models.Model):
    """
    Google Auth Token storage model
    """

    id = models.OneToOneField(User, primary_key=True, related_name='google_id')
    credential = CredentialsField()

    class Meta:
        app_label = 'main'
