from onadata.libs.utils.timing import last_modified_header, get_date


class LastModifiedMixin(object):

    last_modified_field = 'modified'

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET':
            obj = None

            if hasattr(self, 'object_list'):
                obj = self.object_list.last()

            if hasattr(self, 'object'):
                obj = self.object

            if obj:
                self.headers.update(
                    last_modified_header(
                        get_date(obj, self.last_modified_field)))

        return super(LastModifiedMixin, self).finalize_response(
            request, response, *args, **kwargs)
