from rest_framework import serializers

from onadata.libs.models.textit_service import TextItService
from onadata.libs.serializers.fields.xform_field import XFormField


class TextItSerializer(serializers.Serializer):
    xform = XFormField()
    auth_token = serializers.CharField(max_length=255, required=True)
    flow_uuid = serializers.CharField(max_length=255, required=True)
    contacts = serializers.CharField(max_length=255, required=True)

    def restore_object(self, attrs, instance=None):

        if instance:
            instance.xform = attrs.get('xform', instance.xform)
            instance.auth_token = attrs.get('auth_token', instance.auth_token)
            instance.flow_uuid = attrs.get('flow_uuid', instance.flow_uuid)
            instance.contacts = attrs.get('contacts', instance.contacts)

        return TextItService(**attrs)
