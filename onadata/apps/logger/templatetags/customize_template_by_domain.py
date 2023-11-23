from django import template
from django.conf import settings
from onadata.apps.api.tools import get_host_domain

register = template.Library()


@register.simple_tag(takes_context=True)
def settings_value(context, setting):
    template_customization = getattr(settings, "TEMPLATE_CUSTOMIZATION", {})
    request = context.get("request")
    domain = get_host_domain(request)
    if domain in template_customization:
        template_setting = template_customization[domain]
    elif "*" in template_customization:
        template_setting = template_customization["*"]
    else:
        template_setting = {}
    return template_setting[setting] if setting in template_setting else ""
