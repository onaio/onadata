from builtins import str as text
from hashlib import md5

MODELS_WITH_DATE_MODIFIED = ('XForm', 'Instance', 'Project', 'Attachment',
                             'MetaData', 'Note', 'OrganizationProfile',
                             'UserProfile', 'Team')


class ETagsMixin(object):
    """
    Applies the Etag on GET responses with status code 200, 201, 202

    self.etag_data - if it is set, the etag is calculated from this data,
        otherwise the date_modifed of self.object or self.object_list is used.
    """

    def set_etag_header(self, etag_value, etag_hash=None):
        if etag_value:
            etag_hash = md5(text(etag_value).encode('utf-8')).hexdigest()
        if etag_hash:
            self.headers.update({'ETag': etag_hash})

    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and not response.streaming and \
                response.status_code in [200, 201, 202]:
            etag_value = None
            if hasattr(self, 'etag_data') and self.etag_data:
                etag_value = str(self.etag_data)
            elif hasattr(self, 'object'):
                if self.object.__class__.__name__ in MODELS_WITH_DATE_MODIFIED:
                    etag_value = self.object.date_modified

            if hasattr(self, 'etag_hash') and self.etag_hash:
                self.set_etag_header(None, self.etag_hash)
            else:
                self.set_etag_header(etag_value)

        return super(ETagsMixin, self).finalize_response(
            request, response, *args, **kwargs
        )
