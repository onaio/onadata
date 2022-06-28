# -*- coding: utf-8 -*-
"""
The charts_snippet custom template tag functions.
"""
from django import template

register = template.Library()


@register.inclusion_tag("charts_snippet.html", takes_context=True)
def charts_snippet(context, summaries):
    """Provide chart summaries data to a chart template."""
    return {"summaries": summaries, "CSP_NONCE": context["CSP_NONCE"]}
