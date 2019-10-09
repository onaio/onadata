"""
ODK token model class
"""
import binascii
import os

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save

from django_digest.models import (_persist_partial_digests,
                                  _prepare_partial_digests)

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
ODK_TOKEN_LENGTH = getattr(settings, 'ODK_TOKEN_LENGTH', 7)


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
        return binascii.hexlify(os.urandom(ODK_TOKEN_LENGTH)).decode()

    def __str__(self):
        return self.key


def _post_save_prepare_and_persist_partial_digests(sender,
                                                   instance=None,
                                                   **kwargs):
    if instance:
        _prepare_partial_digests(instance.user, instance.key)
        _persist_partial_digests(instance.user)


post_save.connect(
    _post_save_prepare_and_persist_partial_digests, sender=ODKToken)
