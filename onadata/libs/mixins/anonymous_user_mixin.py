from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404


class AnonymousUserMixin(object):

    def get_queryset(self):
        """Set AnonymousUser from the database to allow object permissions."""
        if self.request and self.request.user.is_anonymous():
            self.request.user = get_object_or_404(
                User, username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)

        return super(AnonymousUserMixin, self).get_queryset()
