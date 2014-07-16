from django.conf import settings


url = False
if hasattr(settings, 'KOBOFORM_SERVER') and settings.KOBOFORM_SERVER:
    server = settings.KOBOFORM_SERVER
    if settings.KOBOFORM_SERVER_PORT:
        server += ':%s' % (settings.KOBOFORM_SERVER_PORT)
    url = '%s://%s' % (settings.KOBOFORM_SERVER_PROTOCOL, server)
else:
    url = False

active = bool(url)

autoredirect = active
if active and hasattr(settings, 'KOBOFORM_LOGIN_AUTOREDIRECT'):
    autoredirect = settings.KOBOFORM_LOGIN_AUTOREDIRECT

def redirect_url(url_param):
    if url:
        return url + url_param

def login_url(next_kobocat_url=False, next_url=False):
    if url:
        url_param = url + '/accounts/login/'
        if next_kobocat_url:
            next_url = '/kobocat%s' % next_kobocat_url
        if next_url:
            url_param += "?next=%s" % next_url
        return url_param
