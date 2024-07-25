# -*- coding: utf-8 -*-
"""
Implements MultiLookupMixin class

Looks up an object using multiple lookup fields.
"""
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework.exceptions import ParseError


class MultiLookupMixin:  # pylint: disable=too-few-public-methods
    """
    Implements MultiLookupMixin class

    Looks up an object using multiple lookup fields.
    """

    def get_object(self, queryset=None):
        """Looks up an object using multiple lookup fields."""
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {}
        serializer = self.get_serializer()
        lookup_fields = getattr(self, "lookup_fields", [])

        for field in lookup_fields:
            lookup_field = field

            if lookup_field in serializer.get_fields():
                k = serializer.get_fields()[lookup_field]

                if isinstance(k, serializers.HyperlinkedRelatedField):
                    if k.source:
                        lookup_field = k.source
                    lookup_field = f"{lookup_field}__{k.lookup_field}"

            if self.kwargs.get(field, None) is None:
                raise ParseError(f"Expected URL keyword argument `{field}`.")
            filter_kwargs[lookup_field] = self.kwargs[field]

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
