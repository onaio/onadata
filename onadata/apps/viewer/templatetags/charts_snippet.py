from django import template

register = template.Library()


@register.inclusion_tag("charts_snippet.html", takes_context=True)
def charts_snippet(context, summaries):
    return {"summaries": summaries, "CSP_NONCE": context["CSP_NONCE"]}
