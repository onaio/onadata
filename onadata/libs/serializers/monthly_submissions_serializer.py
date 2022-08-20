# -*- coding: utf-8 -*-
"""
Monthly submissions serializer
"""
from rest_framework import serializers


class MonthlySubmissionsListSerializer(serializers.ListSerializer):
    """
    Monthly submissions serializer
    """

    def update(self, instance, validated_data):
        pass

    def to_representation(self, data):
        result = super().to_representation(data)
        result_dictionary = {}
        for i in result:
            label = "public" if i["xform__shared"] else "private"
            result_dictionary[label] = i["num_instances"]
        return [result_dictionary]


class MonthlySubmissionsSerializer(serializers.Serializer):
    """
    Monthly submissions serializer
    """

    class Meta:
        list_serializer_class = MonthlySubmissionsListSerializer

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def to_representation(self, instance):
        """
        Returns the total number of private/public submissions for a user
        """
        return instance
