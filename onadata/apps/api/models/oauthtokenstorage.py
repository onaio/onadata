# -*- coding: utf-8 -*-
"""
Oauth2 token storage model class
"""

from django.db import models
from jsonfield import JSONField
from django.conf import settings


class OauthStorageModel(models.Model):
    """
    Oauth2 Token storage model
    """

    id = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True,
        on_delete=models.CASCADE)
    credential = JSONField(null=True)

    class Meta:
        app_label = 'api'
