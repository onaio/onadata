import json

from rest_framework import serializers

from django.core.validators import ValidationError


class JsonField(serializers.WritableField):

    def to_native(self, value):
        if isinstance(value, basestring):
            return json.loads(value)

        return value

    def from_native(self, value):
        if isinstance(value, basestring):
            try:
                return json.loads(value)
            except ValueError as e:
                # invalid json
                raise ValidationError(unicode(e))

        return value

    @classmethod
    def to_json(cls, data):
        if isinstance(data, basestring):
            return json.loads(data)
        return data
