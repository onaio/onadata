from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404


class XFormIdStringLookupMixin(object):
    lookup_id_string = 'id_string'

    def get_object(self, queryset=None):
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
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, self.lookup_field)
            )

        filter_kwargs = {lookup_field: lookup}
        obj = get_object_or_404(queryset, **filter_kwargs)

        self.check_object_permissions(self.request, obj)

        return obj
