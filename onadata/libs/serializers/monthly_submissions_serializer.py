"""
Monthly submissions serializer
"""
from rest_framework import serializers


class MonthlySubmissionsListSerializer(serializers.ListSerializer):

    def to_representation(self, data):
        result = super(MonthlySubmissionsListSerializer,
                       self).to_representation(data)
        result_dictionary = {}
        for i in result:
            label = 'public' if i['xform__shared'] else 'private'
            result_dictionary[label] = i['num_instances']
        return [result_dictionary]


class MonthlySubmissionsSerializer(serializers.Serializer):

    class Meta:
        list_serializer_class = MonthlySubmissionsListSerializer

    def to_representation(self, instance):
        """
        Returns the total number of private/public submissions for a user
        """
        return instance
