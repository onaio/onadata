from django.contrib.auth.models import User
from django.db import models
from oauth2client.contrib.django_util.models import CredentialsField


class TokenStorageModel(models.Model):
    id = models.OneToOneField(User, primary_key=True, related_name='google_id')
    credential = CredentialsField()

    class Meta:
        app_label = 'main'
