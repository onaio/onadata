# -*- coding: utf-8 -*-
"""
XForm id_strng lookup mixin class

Looks up an XForm using the id_string.
"""
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404


class XFormIdStringLookupMixin:  # pylint: disable=too-few-public-methods
    """
    XForm id_strng lookup mixin class

    Looks up an XForm using the id_string.
    """

    lookup_id_string = "id_string"

    def get_object(self, queryset=None):
        """Looks up an XForm object using the ``id_string``

        Returns the XForm object or raises a 404 HTTP response exception
        """
        if queryset is None:
            queryset = self.filter_queryset(self.get_queryset())

        lookup_field = self.lookup_field
        lookup = self.kwargs.get(lookup_field)

        if lookup is not None:
            try:
                int(lookup)
            except ValueError:
                lookup_field = self.lookup_id_string
        else:
            raise ImproperlyConfigured(
                f"Expected view {self.__class__.__name__} to be called with a "
                f'URL keyword argument named "{self.lookup_field}". '
                "Fix your URL conf, or set the `.lookup_field` "
                "attribute on the view correctly."
            )

        filter_kwargs = {lookup_field: lookup}
        obj = get_object_or_404(queryset, **filter_kwargs)

        self.check_object_permissions(self.request, obj)

        return obj
