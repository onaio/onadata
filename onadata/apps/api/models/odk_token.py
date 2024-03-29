# -*- coding: utf-8 -*-
"""
ODK token model module
"""
import binascii
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _

from cryptography.fernet import Fernet
from django_digest.models import _persist_partial_digests, _prepare_partial_digests

AUTH_USER_MODEL = get_user_model()
ODK_TOKEN_LENGTH = getattr(settings, "ODK_TOKEN_LENGTH", 7)
ODK_TOKEN_FERNET_KEY = getattr(settings, "ODK_TOKEN_FERNET_KEY", "")
ODK_TOKEN_LIFETIME = getattr(settings, "ODK_KEY_LIFETIME", 7)


class ODKToken(models.Model):
    """
    ODK Token class
    """

    ACTIVE = "1"
    INACTIVE = "2"
    STATUS_CHOICES = ((ACTIVE, _("Active")), (INACTIVE, _("Inactive")))

    key = models.CharField(max_length=150, primary_key=True)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(
        "Status", choices=STATUS_CHOICES, default=ACTIVE, max_length=1
    )
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(blank=True, null=True)

    class Meta:
        app_label = "api"

    def _generate_partial_digest(self, raw_key):
        """
        Generates the partial digests for ODK Authentication
        """
        _prepare_partial_digests(self.user, raw_key)

    def check_key(self, key):
        """
        Check that the passed in key matches the stored hashed key
        """
        return self.raw_key == key

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        if not self.key:
            self.key = self.generate_key()

        return super().save(*args, **kwargs)

    def generate_key(self):
        """
        Generates and returns ODK Token key encrypted with the Fernet cryptography
        scheme.
        """
        key = binascii.hexlify(os.urandom(ODK_TOKEN_LENGTH)).decode("utf-8")
        self._generate_partial_digest(key)
        return _encrypt_key(key)

    def __str__(self):
        return self.key

    @property
    def raw_key(self):
        """
        Decrypts the key and returns it in its Raw Form
        """
        fernet = Fernet(ODK_TOKEN_FERNET_KEY)
        return fernet.decrypt(self.key.encode("utf-8"))


def _encrypt_key(raw_key):
    """
    Encrypts the ODK Token using the ODK_TOKEN_SECRET through
    the fernet cryptography scheme
    """
    fernet = Fernet(ODK_TOKEN_FERNET_KEY)
    return fernet.encrypt(raw_key.encode("utf-8")).decode("utf-8")


# pylint: disable=unused-argument
def _post_save_persist_partial_digests(sender, instance=None, **kwargs):
    if instance:
        _persist_partial_digests(instance.user)


# pylint: disable=unused-argument
def _post_save_set_expiry_date(sender, instance=None, **kwargs):
    if instance and not instance.expires:
        expiry_date = instance.created + timedelta(days=ODK_TOKEN_LIFETIME)
        instance.expires = expiry_date.astimezone(instance.created.tzinfo)
        instance.save()


post_save.connect(_post_save_persist_partial_digests, sender=ODKToken)

post_save.connect(_post_save_set_expiry_date, sender=ODKToken)
