class TotalHeaderMixin(object):
    total_count = None

    def finalize_response(self, request, response, *args, **kwargs):
        if self.total_count is not None:
            self.headers.update({'X-total': self.total_count})

        return super(TotalHeaderMixin, self).finalize_response(
            request, response, *args, **kwargs)
