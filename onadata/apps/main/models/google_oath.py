# -*- coding: utf-8 -*-
"""
Google auth token storage model class
"""
import base64
import pickle
import jsonpickle

from django.conf import settings
from django.db import models
from django.utils import encoding

from google.oauth2.credentials import Credentials


class CredentialsField(models.Field):
    """
    Django ORM field for storing OAuth2 Credentials.
    Modified version of
    https://github.com/onaio/oauth2client/blob/master/oauth2client/contrib/django_util/models.py
    """

    def __init__(self, *args, **kwargs):
        if 'null' not in kwargs:
            kwargs['null'] = True
        super(CredentialsField, self).__init__(*args, **kwargs)

    def get_internal_type(self):
        return 'BinaryField'

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
        elif isinstance(value, Credentials):
            return value
        else:
            try:
                return jsonpickle.decode(
                    base64.b64decode(encoding.smart_bytes(value)).decode())
            except ValueError:
                return pickle.loads(
                    base64.b64decode(encoding.smart_bytes(value)))

    def get_prep_value(self, value):
        """Overrides ``models.Field`` method. This is used to convert
        the value from an instances of this class to bytes that can be
        inserted into the database.
        """
        if value is None:
            return None
        else:
            return encoding.smart_text(
                base64.b64encode(jsonpickle.encode(value).encode()))

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

    id = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True, related_name='google_id',
        on_delete=models.CASCADE)
    credential = CredentialsField()

    class Meta:
        app_label = 'main'
