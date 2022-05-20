# -*- coding: utf-8 -*-
"""
Temporary token authorization model class
"""
import binascii
import os

from django.contrib.auth import get_user_model
from django.db import models


class TempToken(models.Model):

    """
    The temporary authorization token model.
    """

    key = models.CharField(max_length=40, primary_key=True)
    user = models.OneToOneField(
        get_user_model(), related_name="_user", on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super().save(*args, **kwargs)

    def generate_key(self):  # pylint: disable=no-self-use
        """Generates a token key."""
        return binascii.hexlify(os.urandom(20)).decode()

    def __str__(self):
        return self.key
