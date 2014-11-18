from django.conf import settings
from django.contrib.sites.models import Site


def google_analytics(request):
    ga_pid = getattr(settings, 'GOOGLE_ANALYTICS_PROPERTY_ID', False)
    ga_domain = getattr(settings, 'GOOGLE_ANALYTICS_DOMAIN', False)
    ga_site_verification = getattr(settings, 'GOOGLE_SITE_VERIFICATION', False)
    return {
        'GOOGLE_ANALYTICS_PROPERTY_ID': ga_pid,
        'GOOGLE_ANALYTICS_DOMAIN': ga_domain,
        'GOOGLE_SITE_VERIFICATION': ga_site_verification
    }


def site_name(request):
    site_id = getattr(settings, 'SITE_ID', None)
    try:
        site = Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        site_name = 'example.org'
    else:
        site_name = site.name
    return {'SITE_NAME': site_name}

def base_url(request):
    """
    Return a BASE_URL template context for the current request.
    """
    if request.is_secure():
        scheme = 'https://'
    else:
        scheme = 'http://'
        
    return {'BASE_URL': scheme + request.get_host(),}
