from django import template


register = template.Library()


@register.filter(name='lookup')
def lookup(value, arg):
    return value.get(arg)
