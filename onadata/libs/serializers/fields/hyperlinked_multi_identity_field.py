# -*- coding: utf-8 -*-
"""
The HyperlinkedIdentityField class - multi-lookup identity fields.
"""
from rest_framework import serializers
from rest_framework.reverse import reverse


class HyperlinkedMultiIdentityField(serializers.HyperlinkedIdentityField):
    """
    The HyperlinkedIdentityField class - multi-lookup identity fields.
    """

    lookup_fields = (("pk", "pk"),)

    def __init__(self, *args, **kwargs):
        lookup_fields = kwargs.pop("lookup_fields", None)
        self.lookup_fields = lookup_fields or self.lookup_fields

        super().__init__(*args, **kwargs)

    # pylint: disable=redefined-builtin
    def get_url(self, obj, view_name, request, format):
        kwargs = {}
        for slug, field in self.lookup_fields:
            lookup_field = getattr(obj, field)
            kwargs[slug] = lookup_field

        return reverse(view_name, kwargs=kwargs, request=request, format=format)
