import json

import urllib
import urllib2

from oauth2client.client import OAuth2WebServerFlow
from django.conf import settings

google_flow = OAuth2WebServerFlow(
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    scope=' '.join(
        ['https://docs.google.com/feeds/',
         'https://spreadsheets.google.com/feeds/',
         'https://www.googleapis.com/auth/drive.file']),
    redirect_uri=settings.GOOGLE_STEP2_URI)


def get_refreshed_token(token):
    data = urllib.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'refresh_token': token.refresh_token,
        'grant_type': 'refresh_token'})
    request = urllib2.Request(
        url='https://accounts.google.com/o/oauth2/token',
        data=data)
    request_open = urllib2.urlopen(request)
    response = request_open.read()
    request_open.close()
    tokens = json.loads(response)
    token.access_token = tokens['access_token']
    return token
