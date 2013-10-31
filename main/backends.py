from django.contrib.auth.models import User
from django.contrib.auth.backends import RemoteUserBackend


class ModelBackend(RemoteUserBackend):
    # Don't create users that don't exist
    create_unknown_user = False

    def authenticate(self, username=None, password=None):
        """ Case insensitive username """
        try:
            user = User.objects.get(username__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

