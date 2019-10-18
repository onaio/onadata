"""
ODK token model class
"""
import binascii
import os

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save

from cryptography.fernet import Fernet
from django_digest.models import (_persist_partial_digests,
                                  _prepare_partial_digests)

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
ODK_TOKEN_LENGTH = getattr(settings, 'ODK_TOKEN_LENGTH', 7)
ODK_TOKEN_FERNET_KEY = getattr(settings, 'ODK_TOKEN_FERNET_KEY')


class ODKToken(models.Model):
    """
    ODK Token class
    """
    key = models.CharField(max_length=255, primary_key=True)
    user = models.OneToOneField(
        AUTH_USER_MODEL, related_name='odk_token', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'api'

    def _encrypt_key(self, raw_key):
        """
        Encrypts the ODK Token using the ODK_TOKEN_SECRET through
        the fernet cryptography scheme
        """
        fernet = Fernet(ODK_TOKEN_FERNET_KEY)
        return fernet.encrypt(raw_key.encode('utf-8'))

    def _generate_partial_digest(self, raw_key):
        """
        Generates the partial digests for ODK Authentication
        """
        _prepare_partial_digests(self.user, raw_key)

    def check_key(self, key):
        """
        Check that the passed in key matches the stored hashed key
        """
        fernet = Fernet(ODK_TOKEN_FERNET_KEY)
        raw_key = fernet.decrypt(self.key.encode('utf-8'))
        return raw_key == key

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ODKToken, self).save(*args, **kwargs)

    def generate_key(self):
        key = binascii.hexlify(os.urandom(ODK_TOKEN_LENGTH)).decode()
        self._generate_partial_digest(key)
        return self._encrypt_key(key)

    def __str__(self):
        return self.key


def _post_save_persist_partial_digests(sender, instance=None, **kwargs):
    if instance:
        _persist_partial_digests(instance.user)


post_save.connect(
    _post_save_persist_partial_digests, sender=ODKToken)
