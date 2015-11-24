import json

from rest_framework import serializers


class JsonField(serializers.Field):

    def to_representation(self, value):
        if isinstance(value, basestring):
            return json.loads(value)

        return value

    def to_internal_value(self, value):
        if isinstance(value, basestring):
            try:
                return json.loads(value)
            except ValueError as e:
                # invalid json
                raise serializers.ValidationError(unicode(e))

        return value

    @classmethod
    def to_json(cls, data):
        if isinstance(data, basestring):
            return json.loads(data)

        return data
