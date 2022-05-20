# -*- coding: utf-8 -*-
"""
Google auth token storage model class
"""
import base64
import pickle

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import encoding

import jsonpickle
from google.oauth2.credentials import Credentials


class CredentialsField(models.Field):
    """
    Django ORM field for storing OAuth2 Credentials.
    Modified version of
    https://github.com/onaio/oauth2client/blob/master/oauth2client/contrib/django_util/models.py
    """

    def __init__(self, *args, **kwargs):
        if "null" not in kwargs:
            kwargs["null"] = True
        super().__init__(*args, **kwargs)

    def get_internal_type(self):
        return "BinaryField"

    # pylint: disable=unused-argument
    def from_db_value(self, value, expression, connection, context=None):
        """Overrides ``models.Field`` method. This converts the value
        returned from the database to an instance of this class.
        """
        return self.to_python(value)

    def to_python(self, value):
        """Overrides ``models.Field`` method. This is used to convert
        bytes (from serialization etc) to an instance of this class"""
        if value is None:
            return None
        if isinstance(value, Credentials):
            return value
        try:
            return jsonpickle.decode(
                base64.b64decode(encoding.smart_bytes(value)).decode()
            )
        except ValueError:
            return pickle.loads(base64.b64decode(encoding.smart_bytes(value)))

    def get_prep_value(self, value):
        """Overrides ``models.Field`` method. This is used to convert
        the value from an instances of this class to bytes that can be
        inserted into the database.
        """
        if value is None:
            return None
        return encoding.smart_str(base64.b64encode(jsonpickle.encode(value).encode()))

    def value_to_string(self, obj):
        """Convert the field value from the provided model to a string.
        Used during model serialization.
        Args:
            obj: db.Model, model object
        Returns:
            string, the serialized field value
        """
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


class TokenStorageModel(models.Model):
    """
    Google Auth Token storage model
    """

    # pylint: disable=invalid-name
    id = models.OneToOneField(
        get_user_model(),
        primary_key=True,
        related_name="google_id",
        on_delete=models.CASCADE,
    )
    credential = CredentialsField()

    class Meta:
        app_label = "main"
