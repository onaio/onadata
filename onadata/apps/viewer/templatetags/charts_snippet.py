from django import template
register = template.Library()


@register.inclusion_tag('charts_snippet.html')
def charts_snippet(summaries):
    return {'summaries': summaries}
