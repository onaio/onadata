import hashlib


class ETagsMixin(object):

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET':

            m = hashlib.md5()
            m.update(str(response.data))
            hash_value = m.hexdigest()
            self.headers.update({'ETag': hash_value})

        return super(ETagsMixin, self).finalize_response(
            request, response, *args, **kwargs)
