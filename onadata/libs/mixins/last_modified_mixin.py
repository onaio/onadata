import types
from onadata.libs.utils.timing import last_modified_header, get_date
import hashlib


class LastModifiedMixin(object):

    last_modified_field = 'modified'
    last_modified_date = None

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET':
            if self.last_modified_date is not None:
                self.headers.update(
                    last_modified_header(self.last_modified_date))
            else:
                obj = None
                if hasattr(self, 'object_list'):
                    if not isinstance(self.object_list, types.GeneratorType):
                        obj = self.object_list.latest('date_modified')

                if hasattr(self, 'object'):
                    obj = self.object

                if not obj:
                    obj = self.queryset.last()

                if response.status_code < 400:
                    self.headers.update(last_modified_header(get_date(obj)))

        return super(LastModifiedMixin, self).finalize_response(
            request, response, *args, **kwargs)
