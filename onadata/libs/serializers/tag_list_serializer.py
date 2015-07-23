from django.utils.translation import ugettext as _

from rest_framework import serializers


class TagListSerializer(serializers.Field):

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError(_(u"expected a list of data"))

        return data

    def to_representation(self, obj):
        if obj is None:
            return super(TagListSerializer, self).to_representation(obj)

        if not isinstance(obj, list):
            return [tag.name for tag in obj.all()]

        return obj
