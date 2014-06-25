from django.conf import settings

koboform_url = False
if hasattr(settings, 'KOBOFORM_SERVER') and settings.KOBOFORM_SERVER:
    server = settings.KOBOFORM_SERVER
    if settings.KOBOFORM_SERVER_PORT:
        server += ':%s' % (settings.KOBOFORM_SERVER_PORT)
    koboform_url = '%s://%s' % (settings.KOBOFORM_SERVER_PROTOCOL, server)

def koboform_integration(request):
    return {
        u'koboform_url': koboform_url,
    }
