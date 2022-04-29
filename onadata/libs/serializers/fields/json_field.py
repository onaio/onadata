# -*- coding: utf-8 -*-
"""
A string is represented as valid JSON and is accessible as a dictionary and vis-a-vis.
"""
import json

from rest_framework import serializers


class JsonField(serializers.Field):
    """
    Deserialize a string instance containing a JSON document to a Python object.
    """

    def to_representation(self, value):
        """
        Deserialize ``value`` a `str` instance containing a
        JSON document to a Python object.
        """
        if isinstance(value, str):
            return json.loads(value)
        return value

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                return json.loads(data)
            except ValueError as e:
                # invalid json
                raise serializers.ValidationError(str(e))
        return data

    @classmethod
    def to_json(cls, data):
        """Returns the JSON string as a dictionary."""
        if isinstance(data, str):
            return json.loads(data)
        return data
