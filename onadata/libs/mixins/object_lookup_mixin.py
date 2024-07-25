# -*- coding: utf-8 -*-
"""
Implements ObjectLookupMixin class

Incase the lookup is on an object that has been hyperlinked
then update the queryset filter appropriately
"""
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404


class ObjectLookupMixin:  # pylint: disable=too-few-public-methods
    """
    Implements ObjectLookupMixin class

    Incase the lookup is on an object that has been hyperlinked
    then update the queryset filter appropriately
    """

    def get_object(self, queryset=None):
        """
        Incase the lookup is on an object that has been hyperlinked
        then update the queryset filter appropriately
        """
        if self.kwargs.get(self.lookup_field, None) is None:
            raise ParseError(f"Expected URL keyword argument `{self.lookup_field}`.")
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        filter_kwargs = {}
        serializer = self.get_serializer()
        lookup_field = self.lookup_field

        if self.lookup_field in serializer.get_fields():
            k = serializer.get_fields()[self.lookup_field]
            if isinstance(k, serializers.HyperlinkedRelatedField):
                lookup_field = f"{self.lookup_field}__{k.lookup_field}"

        filter_kwargs[lookup_field] = self.kwargs[self.lookup_field]

        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
