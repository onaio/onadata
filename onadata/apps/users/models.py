"""Implement a custom user model."""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator


class OnadataUsernameValidator(UnicodeUsernameValidator):
    regex = r"^\w+$"


class OnadataUser(AbstractUser):
    username_validator = OnadataUsernameValidator
