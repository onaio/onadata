import types

from django.utils.timezone import now
from hashlib import md5

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm


class ETagsMixin(object):
    """
    Applies the Etag on GET responses with status code 200, 201, 202

    self.etag_data - if it is set, the etag is calculated from this data,
        otherwise the date_modifed of self.object or self.object_list is used.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming and \
                response.status_code in [200, 201, 202]:
            etag_value = obj = None
            if hasattr(self, 'etag_data') and self.etag_data:
                etag_value = str(self.etag_data)
            elif hasattr(self, 'object_list'):
                if not isinstance(self.object_list, types.GeneratorType):
                    obj = self.object_list.last()
                    if isinstance(obj, (XForm, Instance)):
                        etag_value = self.object_list\
                            .order_by('-date_modified')\
                            .values_list('date_modified', flat=True).first()
            elif hasattr(self, 'object'):
                if isinstance(self.object, (XForm, Instance)):
                    etag_value = self.object.date_modified

            hash_value = md5(
                '%s' % (etag_value if etag_value is not None else now())
            ).hexdigest()
            value = "W/{}".format(hash_value)

            if etag_value:
                self.headers.update({'ETag': value})

        return super(ETagsMixin, self).finalize_response(
            request, response, *args, **kwargs)
