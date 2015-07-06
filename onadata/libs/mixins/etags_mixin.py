import hashlib


class ETagsMixin(object):

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming:
            m = hashlib.md5()
            m.update(str(response.data))
            hash_value = m.hexdigest()
            value = "W/{}".format(hash_value)
            self.headers.update({'ETag': value})

        return super(ETagsMixin, self).finalize_response(
            request, response, *args, **kwargs)
