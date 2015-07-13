import hashlib


class ETagsMixin(object):

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming and \
                response.status_code in [200, 201, 202]:
            m = hashlib.md5()
            m.update(str(response.data))
            hash_value = m.hexdigest()
            value = "W/{}".format(hash_value)
            self.headers.update({'ETag': value})

        return super(ETagsMixin, self).finalize_response(
            request, response, *args, **kwargs)
