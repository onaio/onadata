import gspread

from oauth2client.django_orm import Storage
from oauth2client import client as google_client

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseRedirect

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.main.views import home
from onadata.libs.utils.google import google_flow, get_refreshed_token


def google_oauth2_request(request):
    token = None
    if request.user.is_authenticated():
        try:
            storage = Storage(TokenStorageModel, 'id', request.user, 'credential')
            credential = storage.get()
        except TokenStorageModel.DoesNotExist:
            pass
        else:
            token = credential.access_token
    elif request.session.get('access_token'):
        token = request.session.get('access_token')
    if token is not None:
        google_creds = google_client.OAuth2Credentials.from_json(token)
        gc = gspread.authorize(google_creds)

        docs_feed = gc.get_spreadsheets_feed()
        _l='<ul>'
        for entry in docs_feed.entry:
            _l += '<li>%s</li>' % entry.title.text
            print entry.title.text
        _l += '</ul>'
        return HttpResponse(_l)
    return HttpResponseRedirect(google_flow.step1_get_authorize_url())


def google_auth_return(request):
    if 'code' not in request.REQUEST:
        return HttpResponse(u"Invalid Request")
    if request.user.is_authenticated():

        storage = Storage(TokenStorageModel, 'id', request.user,
                          'credential')
        code = request.REQUEST.get('code')
        google_creds = google_flow.step2_exchange(code)
        storage.put(google_creds)
    else:
        code = request.REQUEST.get('code')
        google_creds = google_flow.step2_exchange(code)
        request.session["access_token"] = google_creds.to_json()
    if request.session.get('google_redirect_url'):
        return HttpResponseRedirect(request.session.get('google_redirect_url'))
    return HttpResponseRedirect(reverse(home))


def refresh_access_token(token, user):
    token = get_refreshed_token(token)
    if not user.is_authenticated():
        return token
    try:
        ts = TokenStorageModel.objects.get(id=user)
    except TokenStorageModel.DoesNotExist:
        ts = TokenStorageModel(id=user)
    ts.token = gdata.gauth.token_to_blob(token)
    ts.save()
    return token
