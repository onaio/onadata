class AddXTotalHeaderMixin(object):

    def finalize_response(self, request, response, *args, **kwargs):
        if self.x_total_count is not None:
            self.headers.update({'X-total': self.x_total_count})

        return super(AddXTotalHeaderMixin, self).finalize_response(
            request, response, *args, **kwargs)
