from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from onadata.apps.logger.models import OpenData, XForm
from django.shortcuts import get_object_or_404


class OpenDataSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, required=True)
    clazz = serializers.CharField(max_length=50, required=False)
    object_id = serializers.IntegerField(required=False)
    active = serializers.BooleanField(required=False)

    class Meta:
        model = OpenData
        exclude = ('date_created', 'date_modified', 'content_type', 'id')

    def create(self, validated_data):
        name = validated_data.get('name')
        clazz = validated_data.get('clazz')
        object_id = validated_data.get('object_id')
        op = None

        if clazz == 'xform':
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
        instance.name = validated_data.get('name', instance.name)
        instance.object_id = validated_data.get(
            'object_id', instance.object_id
        )
        instance.active = validated_data.get('active', instance.active)
        instance.save()

        return instance
