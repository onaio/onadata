import collections

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from onadata.apps.logger.models import OpenData, XForm
from django.shortcuts import get_object_or_404


def get_data(request_data, update=False):
    '''
    return a namedtuple with error, message and data values.
    '''
    fields = ['object_id', 'data_type', 'name']
    results = collections.namedtuple('results', 'error message data')
    if not update:
        if not set(fields).issubset(request_data.keys()):
            return results(
                error=True,
                message="Fields object_id, data_type and name are required.",
                data=None
            )

    fields.append('active')

    # check if invalid fields are provided
    if any(a not in fields for a in request_data.keys()):
        return results(
            error=True,
            message="Valid fields are object_id, data_type and name.",
            data=None
        )

    data = {}
    for key in fields:
        available = request_data.get(key) is not None
        available and data.update({key: request_data.get(key)})

    return results(error=False, message=None, data=data)


class OpenDataSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, required=True)
    data_type = serializers.CharField(max_length=50, required=False)
    object_id = serializers.IntegerField(required=False)
    active = serializers.BooleanField(required=False)

    class Meta:
        model = OpenData
        exclude = ('date_created', 'date_modified', 'content_type', 'id')

    def create(self, validated_data):
        results = get_data(validated_data)
        if results.error:
            raise serializers.ValidationError(results.message)

        name = validated_data.get('name')
        data_type = validated_data.get('data_type')
        object_id = validated_data.get('object_id')
        op = None

        if data_type == 'xform':
            xform = get_object_or_404(XForm, id=object_id)
            ct = ContentType.objects.get_for_model(xform)

            op, created = OpenData.objects.get_or_create(
                object_id=object_id,
                defaults={
                    'name': name,
                    'content_type': ct,
                    'content_object': xform,
                }
            )

        return op

    def update(self, instance, validated_data):
        results = get_data(validated_data, update=True)
        if results.error:
            raise serializers.ValidationError(results.message)

        instance.name = validated_data.get('name', instance.name)
        instance.object_id = validated_data.get(
            'object_id', instance.object_id
        )
        instance.active = validated_data.get('active', instance.active)
        instance.save()

        return instance
