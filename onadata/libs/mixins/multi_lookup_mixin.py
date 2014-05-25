from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ParseError


class MultiLookupMixin(object):
    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {}
        serializer = self.get_serializer()
        lookup_fields = getattr(self, 'lookup_fields', [])

        for field in lookup_fields:
            lookup_field = field

            if lookup_field in serializer.get_fields():
                k = serializer.get_fields()[lookup_field]

                if isinstance(k, serializers.HyperlinkedRelatedField):
                    if k.source:
                        lookup_field = k.source
                    lookup_field = '%s__%s' % (lookup_field, k.lookup_field)

            if self.kwargs.get(field, None) is None:
                raise ParseError(
                    'Expected URL keyword argument `%s`.' % field
                )
            filter_kwargs[lookup_field] = self.kwargs[field]

        obj = get_object_or_404(queryset,  **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
