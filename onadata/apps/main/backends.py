from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend as DjangoModelBackend

User = get_user_model()


class ModelBackend(DjangoModelBackend):
    def authenticate(self, username=None, password=None):
        """Username is case insensitive."""
        try:
            user = User.objects.get(username__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
