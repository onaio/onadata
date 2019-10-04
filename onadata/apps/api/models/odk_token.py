"""
ODK token model class
"""
import binascii
import os

from django.conf import settings
from django.db import models

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class ODKToken(models.Model):
    """
    ODK Token class
    """
    key = models.CharField(max_length=40, primary_key=True)
    user = models.OneToOneField(
        AUTH_USER_MODEL, related_name='odk_token', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'api'

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ODKToken, self).save(*args, **kwargs)

    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()

    def __str__(self):
        return self.key
