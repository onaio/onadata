from rest_framework import serializers


class BooleanField(serializers.BooleanField):
    TRUE_VALUES = ('true', 't', 'True', '1')
    FALSE_VALUES = ('false', 'f', 'False', '0')

    def to_internal_value(self, value):
        if value in self.TRUE_VALUES:
            return True

        if value in self.FALSE_VALUES:
            return False

        return value
