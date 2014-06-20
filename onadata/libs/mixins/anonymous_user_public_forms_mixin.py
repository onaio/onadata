from onadata.apps.logger.models.xform import XForm


class AnonymousUserPublicFormsMixin(object):

    def get_queryset(self):
        """Public forms only for anonymous Users."""
        if self.request and self.request.user.is_anonymous():
            return XForm.objects.filter(shared=True)

        return super(AnonymousUserPublicFormsMixin, self).get_queryset()
