from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend as DjangoModelBackend
from django.db.models import Q


class ModelBackend(DjangoModelBackend):
    def authenticate(self, request=None, username=None, password=None):
        """
        Username is case insensitive. Supports using email in place of username
        """
        user = User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)).first()

        if user and user.check_password(password):
            return user

        return None
