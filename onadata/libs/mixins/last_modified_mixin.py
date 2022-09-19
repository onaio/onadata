# -*- coding: utf-8 -*-
"""
Implements the LastModifiedMixin class

Adds the Last-Modified header to a viewset response.
"""
import types

from onadata.libs.utils.timing import get_date, last_modified_header


class LastModifiedMixin:
    """
    Implements the LastModifiedMixin class

    Adds the Last-Modified header to a viewset response.
    """

    last_modified_field = "modified"
    last_modified_date = None

    def finalize_response(self, request, response, *args, **kwargs):
        """Overrides the finalize_response method

        Adds the Last-Modified header to a viewset response."""
        if request.method == "GET" and response.status_code < 300:
            if self.last_modified_date is not None:
                self.headers.update(last_modified_header(self.last_modified_date))
            else:
                obj = None
                if hasattr(self, "object_list"):
                    generator_type = isinstance(self.object_list, types.GeneratorType)
                    if isinstance(self.object_list, list) and len(self.object_list):
                        obj = self.object_list[len(self.object_list) - 1]
                    elif not isinstance(self.object_list, list) and not generator_type:
                        obj = self.object_list.last()

                if hasattr(self, "object"):
                    obj = self.object

                if not obj:
                    obj = self.queryset.last()

                self.headers.update(last_modified_header(get_date(obj)))

        return super().finalize_response(request, response, *args, **kwargs)
