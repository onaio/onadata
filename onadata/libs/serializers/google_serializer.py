from oauth2client.contrib.django_orm import Storage

from rest_framework import serializers

from onadata.apps.main.models import TokenStorageModel
from onadata.libs.utils.google import google_flow


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
