"""
Monthly submissions serializer
"""
from rest_framework import serializers


class MonthlySubmissionsListSerializer(serializers.ListSerializer):

    def to_representation(self, data):
        result = super(MonthlySubmissionsListSerializer,
                       self).to_representation(data)
        states = [True, False]
        result_dictionary = {}

        def get_result():
            for state in states:
                for i in result:
                    if i['xform__shared'] == state:
                        label = 'public' if state else 'private'
                        result_dictionary[label] = i['num_instances']

        get_result()
        return [result_dictionary]


class MonthlySubmissionsSerializer(serializers.Serializer):

    class Meta:
        list_serializer_class = MonthlySubmissionsListSerializer

    def to_representation(self, instance):
        """
        Returns the total number of private/public submissions for a user
        """
        return instance
