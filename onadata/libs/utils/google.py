from oauth2client.client import OAuth2WebServerFlow
from django.conf import settings

google_flow = OAuth2WebServerFlow(
    client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
    client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
    scope=' '.join(
        ['https://docs.google.com/feeds/',
         'https://spreadsheets.google.com/feeds/',
         'https://www.googleapis.com/auth/drive.file']),
    redirect_uri=settings.GOOGLE_STEP2_URI,  prompt="consent")
