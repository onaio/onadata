# -*- coding: utf-8 -*-
"""
The TextItSerializer - supports creating TextIt integration service.
"""
from django.conf import settings
from rest_framework import serializers

from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.models.textit_service import TextItService
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.libs.utils.common_tags import TEXTIT_DETAILS


class TextItSerializer(serializers.Serializer):
    """
    The TextItSerializer - supports creating TextIt integration service.
    """

    # pylint: disable=invalid-name
    id = serializers.IntegerField(source="pk", read_only=True)
    xform = XFormField()
    auth_token = serializers.CharField(max_length=255, required=True)
    flow_title = serializers.CharField(max_length=255, default="")
    flow_uuid = serializers.CharField(max_length=255, required=True)
    contacts = serializers.CharField(max_length=255, required=True)
    name = serializers.CharField(max_length=50, required=True)
    service_url = serializers.URLField(required=True)
    date_created = serializers.DateTimeField(read_only=True)
    date_modified = serializers.DateTimeField(read_only=True)
    active = serializers.BooleanField(read_only=True)
    inactive_reason = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        meta_data = MetaData.objects.filter(
            data_type=TEXTIT_DETAILS, object_id=instance.xform.pk
        ).first()
        flow_title = ""
        if meta_data:
            flow_title = meta_data.data_value
        text_it = TextItService(
            pk=instance.pk,
            xform=instance.xform,
            service_url=instance.service_url,
            name=instance.name,
            flow_title=flow_title,
        )
        text_it.date_modified = instance.date_modified
        text_it.date_created = instance.date_created
        text_it.active = instance.active
        text_it.inactive_reason = instance.inactive_reason
        text_it.retrieve()
        return super().to_representation(text_it)

    def update(self, instance, validated_data):
        data_value = MetaData.textit(instance.xform) or ""
        values = data_value.split(settings.METADATA_SEPARATOR)
        if len(values) < 3:
            values = ["", "", ""]
        xform = validated_data.get("xform", instance.xform)
        auth_token = validated_data.get("auth_token", values[0])
        flow_uuid = validated_data.get("flow_uuid", values[1])
        contacts = validated_data.get("contacts", values[2])
        name = validated_data.get("name", instance.name)
        service_url = validated_data.get("service_url", instance.service_url)

        instance = TextItService(
            xform,
            service_url,
            name,
            auth_token,
            flow_uuid,
            contacts,
            instance.pk,
            flow_title=validated_data.get("flow_title"),
        )
        instance.save()

        return instance

    def create(self, validated_data):
        instance = TextItService(**validated_data)
        instance.save()

        return instance
