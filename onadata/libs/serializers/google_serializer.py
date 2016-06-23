from oauth2client.contrib.django_orm import Storage

from django.http import HttpResponseRedirect
from rest_framework import serializers
from oauth2client.client import FlowExchangeError

from onadata.apps.main.models import TokenStorageModel
from onadata.libs.utils.api_export_tools import generate_google_web_flow
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.fields.xform_field import XFormField
from onadata.libs.models.google_sheet_service import GoogleSheetService
from onadata.libs.utils.api_export_tools import _get_google_credential
from onadata.libs.utils.common_tags import GOOGLE_SHEET_TITLE,\
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA, GOOGLE_SHEET_ID
from onadata.apps.restservice.models import RestService
from onadata.libs.utils.google_sheets_tools import get_spread_sheet_url


class GoogleCredentialSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=255, required=True)

    def save(self):
        self.is_valid(raise_exception=True)

        try:
            request = self.context.get('request')
            storage = Storage(TokenStorageModel, 'id', request.user,
                              'credential')
            code = self.validated_data['code']
            google_flow = generate_google_web_flow(request)
            google_creds = google_flow.step2_exchange(code)
            google_creds.set_store(storage)
            storage.put(google_creds)
        except FlowExchangeError as e:
            error = {
                u"details": e.message,
            }
            raise serializers.ValidationError(error)


class GoogleSheetsSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    name = serializers.CharField(max_length=50, required=True)
    service_url = serializers.URLField(default="https://drive.google.com",
                                       required=False)
    xform = XFormField()
    google_sheet_title = serializers.CharField(max_length=255, required=True)
    send_existing_data = serializers.BooleanField(default=True)
    sync_updates = serializers.BooleanField(default=True)
    google_sheet_url = serializers.ReadOnlyField(default=None)
    date_created = serializers.DateTimeField(read_only=True)
    date_modified = serializers.DateTimeField(read_only=True)

    class Meta:
        model = RestService

    def to_representation(self, instance):
        google = GoogleSheetService(pk=instance.pk, xform=instance.xform,
                                    service_url=instance.service_url,
                                    name=instance.name)
        google.date_modified = instance.date_modified
        google.date_created = instance.date_created

        google.retrieve()
        return super(GoogleSheetsSerializer, self).to_representation(google)

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
        meta = MetaData.get_google_sheet_details(instance.xform.pk)
        title = meta.get(GOOGLE_SHEET_TITLE)
        sheet_id = meta.get(GOOGLE_SHEET_ID)
        updates = meta.get(UPDATE_OR_DELETE_GOOGLE_SHEET_DATA)
        request = self.context.get('request')
        user = request.user

        pk = validated_data.get('pk', instance.pk)
        name = validated_data.get('name', instance.name)
        xform = validated_data.get('xform', instance.xform)
        google_sheet_title = validated_data.get('google_sheet_title', title)
        google_sheet_url = get_spread_sheet_url(sheet_id)
        send_existing_data = validated_data.get('send_existing_data', False)
        service_url = validated_data.get('service_url', instance.service_url)
        sync_updates = validated_data.get('sync_updates', updates)

        instance = GoogleSheetService(user, xform, service_url, name,
                                      google_sheet_title, send_existing_data,
                                      sync_updates, google_sheet_url, pk)
        instance.save(update=True)

        return instance
