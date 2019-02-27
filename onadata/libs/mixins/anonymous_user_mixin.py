from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

User = get_user_model()


class AnonymousUserMixin(object):

    def get_queryset(self):
        """Set AnonymousUser from the database to allow object permissions."""
        if self.request and self.request.user.is_anonymous():
            self.request.user = get_object_or_404(
                User, username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME)

        return super(AnonymousUserMixin, self).get_queryset()
