from oauth2client.contrib.django_orm import Storage

from django.http import HttpResponseRedirect
from rest_framework import serializers

from onadata.apps.main.models import TokenStorageModel
from onadata.libs.utils.google import google_flow
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.libs.models.google_sheet_service import GoogleSheetService
from onadata.libs.utils.api_export_tools import _get_google_credential
from onadata.libs.utils.common_tags import GOOGLE_SHEET_TITLE,\
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA


class GoogleCredentialSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=255, required=True)

    def save(self):
        self.is_valid(raise_exception=True)

        request = self.context.get('request')
        storage = Storage(TokenStorageModel, 'id', request.user,
                          'credential')
        code = self.validated_data['code']
        google_creds = google_flow.step2_exchange(code)
        google_creds.set_store(storage)
        storage.put(google_creds)


class GoogleSheetsSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    name = serializers.CharField(max_length=50, required=True)
    service_url = serializers.URLField(default="https://drive.google.com")
    xform = XFormField()
    google_sheet_title = serializers.CharField(max_length=255, required=True)
    send_existing_data = serializers.BooleanField(default=True)
    sync_updates = serializers.BooleanField(default=True)

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user and not request.user.is_anonymous():
            response = _get_google_credential(request)
            if isinstance(response, HttpResponseRedirect):
                error = {
                    u"details": u"Google Authorization needed",
                    u"url": response.url
                 }
                raise serializers.ValidationError(error)
        else:
            raise serializers.ValidationError(u"Authentication required")

        return attrs

    def create(self, validated_data):
        # Get the authenticated user
        request = self.context.get('request')
        instance = GoogleSheetService(user=request.user, **validated_data)
        instance.save()

        return instance

    def update(self, instance, validated_data):
        meta = MetaData.get_google_sheet_details(instance.xform)
        title = meta.get(GOOGLE_SHEET_TITLE)
        updates = meta.get(UPDATE_OR_DELETE_GOOGLE_SHEET_DATA)
        request = self.context.get('request')
        user = request.user

        pk = validated_data.get('pk', instance.pk)
        name = validated_data.get('name', instance.name)
        xform = validated_data.get('xform', instance.xform)
        google_sheet_title = validated_data.get('google_sheet_title', title)
        send_existing_data = validated_data.get('send_existing_data', False)
        service_url = validated_data.get('service_url', instance.service_url)
        sync_updates = validated_data.get('sync_updates', updates)

        instance = GoogleSheetService(user, xform, service_url, name,
                                      google_sheet_title, send_existing_data,
                                      sync_updates, pk)
        instance.save()

        return instance
