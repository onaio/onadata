from rest_framework import serializers

from onadata.libs.models.textit_service import TextItService
from onadata.libs.serializers.fields.xform_field import XFormField


class TextItSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    xform = XFormField()
    auth_token = serializers.CharField(max_length=255, required=True)
    flow_uuid = serializers.CharField(max_length=255, required=True)
    contacts = serializers.CharField(max_length=255, required=True)
    name = serializers.CharField(max_length=50, required=True)
    service_url = serializers.URLField(required=True)

    def restore_object(self, attrs, instance=None):

        if instance:
            instance.xform = attrs.get('xform', instance.xform)
            instance.auth_token = attrs.get('auth_token', instance.auth_token)
            instance.flow_uuid = attrs.get('flow_uuid', instance.flow_uuid)
            instance.contacts = attrs.get('contacts', instance.contacts)
            instance.name = attrs.get('name', instance.name)
            instance.service_url = attrs.get('service_url',
                                             instance.service_url)

        return TextItService(**attrs)
