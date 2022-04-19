import json
from builtins import str as text
from rest_framework import serializers


class JsonField(serializers.Field):
    def to_representation(self, value):
        if isinstance(value, str):
            return json.loads(value)
        return value

    def to_internal_value(self, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError as e:
                # invalid json
                raise serializers.ValidationError(text(e))
        return value

    @classmethod
    def to_json(cls, data):
        if isinstance(data, str):
            return json.loads(data)
        return data
