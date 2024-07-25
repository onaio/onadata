# -*- coding: utf-8 -*-
"""
google_analytics and site_name context processor functions.
"""
from django.conf import settings
from django.contrib.sites.models import Site


def google_analytics(request):
    """Returns Google Analytics property id, domain and site verification settings."""
    ga_pid = getattr(settings, "GOOGLE_ANALYTICS_PROPERTY_ID", False)
    ga_domain = getattr(settings, "GOOGLE_ANALYTICS_DOMAIN", False)
    ga_site_verification = getattr(settings, "GOOGLE_SITE_VERIFICATION", False)
    return {
        "GOOGLE_ANALYTICS_PROPERTY_ID": ga_pid,
        "GOOGLE_ANALYTICS_DOMAIN": ga_domain,
        "GOOGLE_SITE_VERIFICATION": ga_site_verification,
    }


def site_name(request):
    """Returns the SITE_NAME/"""
    site_id = getattr(settings, "SITE_ID", None)
    try:
        request_host = request.get_host() if request else None
        name = request_host or Site.objects.get(pk=site_id).name
    except Site.DoesNotExist:
        name = "example.org"

    return {"SITE_NAME": name}
