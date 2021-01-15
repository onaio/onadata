import os
from django.conf import settings
from google_auth_oauthlib.flow import InstalledAppFlow

client_secrets_file = os.path.join(
    settings.PROJECT_ROOT, "settings", "client_secrets.json")

google_flow = InstalledAppFlow.from_client_secrets_file(
    client_secrets_file, scopes=[
        'https://www.googleapis.com/auth/docs',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'])
