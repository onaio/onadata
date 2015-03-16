from django.conf import settings
from rest_framework import serializers

from onadata.apps.main.models.meta_data import MetaData
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
            meta = MetaData.textit(instance.xform)
            values = meta.data_value.split(settings.METADATA_SEPARATOR)
            if len(values) < 3:
                values = ['', '', '']
            xform = attrs.get('xform', instance.xform)
            auth_token = attrs.get('auth_token', values[0])
            flow_uuid = attrs.get('flow_uuid', values[1])
            contacts = attrs.get('contacts', values[2])
            name = attrs.get('name', instance.name)
            service_url = attrs.get('service_url', instance.service_url)

            return TextItService(xform, service_url, name, auth_token,
                                 flow_uuid, contacts, instance.pk)

        return TextItService(**attrs)
