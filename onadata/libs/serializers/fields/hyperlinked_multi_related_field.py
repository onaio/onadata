from rest_framework import serializers
from rest_framework.reverse import reverse


def get_obj_property_value(obj, field):
    """
    Given an object and a field which may have nested properties
    return value of nested property
    >>> class demo: pass
    >>> demo.ls = []
    >>> get_obj_property_value(demo, 'ls.__class__')
    <<< list
    """

    _attr_list = field.split('.')

    if len(_attr_list) > 1:
        tmp_obj = getattr(obj, _attr_list[0])

        return get_obj_property_value(tmp_obj, '.'.join(_attr_list[1:]))

    return getattr(obj, field)


class HyperlinkedMultiRelatedField(serializers.HyperlinkedRelatedField):
    lookup_fields = (('pk', 'pk'), )

    def __init__(self, *args, **kwargs):
        lookup_fields = kwargs.pop('lookup_fields', None)
        self.lookup_fields = lookup_fields or self.lookup_fields

        super(HyperlinkedMultiRelatedField, self).__init__(*args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        kwargs = {}

        for slug, field in self.lookup_fields:
            lookup_field = get_obj_property_value(obj, field)

            kwargs[slug] = lookup_field
        return reverse(
            view_name, kwargs=kwargs, request=request, format=format)
