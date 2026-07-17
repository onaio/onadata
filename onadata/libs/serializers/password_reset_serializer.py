# -*- coding: utf-8 -*-
"""
Password reset serializer.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from onadata.libs.utils.user_auth import invalidate_and_regen_tokens

# pylint: disable=invalid-name
User = get_user_model()


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """
    Custom Password Token Generator Class.
    """

    def _make_hash_value(self, user, timestamp):
        # Include user email alongside user password to the generated token
        # as the user state object that might change after a password reset
        # to produce a token that invalidated.
        login_timestamp = (
            ""
            if user.last_login is None
            else user.last_login.replace(microsecond=0, tzinfo=None)
        )
        return (
            str(user.pk)
            + user.password
            + user.email
            + str(login_timestamp)
            + str(timestamp)
        )


default_token_generator = CustomPasswordResetTokenGenerator()


def get_user_from_uid(uid):
    """
    Return user from base64 encoded ``uid``.
    """
    if uid is None:
        raise serializers.ValidationError(_("uid is required!"))
    try:
        uid = urlsafe_base64_decode(uid)
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        raise serializers.ValidationError(_("Invalid uid {uid}")) from e

    return user


# pylint: disable=too-few-public-methods
class PasswordResetChange:
    """
    Class resets and changes the password.

    Class imitates a model functionality for use with
    PasswordResetChangeSerializer
    """

    def __init__(self, uid, new_password, token):
        self.uid = uid
        self.new_password = new_password
        self.token = token

    def save(self):
        """
        Set a new user password and invalidate/regenerate tokens.
        """
        user = get_user_from_uid(self.uid)
        if user:
            user.set_password(self.new_password)
            user.save()
            invalidate_and_regen_tokens(user)


# pylint: disable=abstract-method
class PasswordResetChangeSerializer(serializers.Serializer):
    """
    Reset and change password serializer.
    """

    uid = serializers.CharField(max_length=50)
    new_password = serializers.CharField(min_length=4, max_length=128)
    token = serializers.CharField(max_length=128)

    def validate_uid(self, value):
        """
        Validate the user uid.
        """
        get_user_from_uid(value)

        return value

    def validate(self, attrs):
        """Validates the generated user token."""
        user = get_user_from_uid(attrs.get("uid"))
        token = attrs.get("token")

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(_(f"Invalid token: {token}"))

        try:
            validate_password(attrs.get("new_password"), user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)

        return attrs

    def create(self, validated_data, instance=None):
        """Set a new user password and invalidate/regenerate tokens."""
        instance = PasswordResetChange(**validated_data)
        instance.save()

        return instance
