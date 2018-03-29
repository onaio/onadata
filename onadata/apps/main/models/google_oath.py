# -*- coding: utf-8 -*-
"""
Google auth token storage model class
"""
from django.conf import settings
from django.db import models
from oauth2client.contrib.django_util.models import CredentialsField


class TokenStorageModel(models.Model):
    """
    Google Auth Token storage model
    """

    id = models.OneToOneField(settings.AUTH_USER_MODEL,
                              primary_key=True, related_name='google_id')
    credential = CredentialsField()

    class Meta:
        app_label = 'main'
