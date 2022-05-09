from typing import Optional

from django.conf import settings
from google_auth_oauthlib.flow import Flow


def create_flow(redirect_uri: Optional[str] = None) -> Flow:
    return Flow.from_client_config(
        settings.GOOGLE_FLOW,
        scopes=['https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/docs',
            'https://www.googleapis.com/auth/drive.file'],
        redirect_uri=redirect_uri or settings.GOOGLE_STEP2_URI)

# google_flow = OAuth2WebServerFlow(
#     client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
#     client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
#     scope=' '.join(
#     redirect_uri=settings.GOOGLE_STEP2_URI,  prompt="consent")
