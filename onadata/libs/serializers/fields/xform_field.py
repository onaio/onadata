# -*- coding: utf-8 -*-
"""
The XFormField class
"""
from rest_framework import serializers

from onadata.apps.logger.models import XForm


class XFormField(serializers.Field):
    """
    The XFormField class
    """

    def to_representation(self, value):
        return value.pk

    def to_internal_value(self, data):
        try:
            int(data)
        except ValueError as exc:
            raise serializers.ValidationError("Invalid form id") from exc
        return XForm.objects.get(pk=data)
