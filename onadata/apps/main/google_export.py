from oauth2client.contrib.django_orm import Storage

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponseBadRequest

from onadata.apps.main.models import TokenStorageModel
from onadata.apps.main.views import home
from onadata.libs.utils.google import google_flow
from oauth2client.client import FlowExchangeError


def google_auth_return(request):
    if 'code' not in request.GET:
        return HttpResponse(u"Invalid Request")
    if request.user.is_authenticated():

        storage = Storage(TokenStorageModel, 'id', request.user,
                          'credential')
        code = request.GET.get('code')
        try:
            google_creds = google_flow.step2_exchange(code)
        except FlowExchangeError as e:
            return HttpResponseBadRequest(str(e))
        google_creds.set_store(storage)
        storage.put(google_creds)
    else:
        code = request.GET.get('code')
        google_creds = google_flow.step2_exchange(code)
        request.session["access_token"] = google_creds.to_json()
    if request.GET.get('return_back_url'):
        return HttpResponseRedirect(request.GET.get('return_back_url'))
    return HttpResponseRedirect(reverse(home))
