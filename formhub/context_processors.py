from django.conf import settings


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
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'example.org')}
