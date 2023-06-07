# -*- coding: utf-8 -*-
"""
Password reset serializer.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from six.moves.urllib.parse import urlparse

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


# pylint: disable=unused-argument,too-many-arguments
def get_password_reset_email(
    user,
    reset_url,
    subject_template_name="registration/password_reset_subject.txt",  # noqa
    email_template_name="api_password_reset_email.html",  # noqa
    token_generator=default_token_generator,
    email_subject=None,
):
    """Creates the subject and email body for password reset email."""
    result = urlparse(reset_url)
    site_name = domain = result.hostname
    encoded_username = urlsafe_base64_encode(bytes(user.username.encode("utf-8")))
    c = {
        "email": user.email,
        "domain": domain,
        "path": result.path,
        "site_name": site_name,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "username": user.username,
        "encoded_username": encoded_username,
        "token": token_generator.make_token(user),
        "protocol": result.scheme if result.scheme != "" else "http",
    }
    # if subject email provided don't load the subject template
    subject = email_subject or loader.render_to_string(subject_template_name, c)
    # Email subject *must not* contain newlines
    subject = "".join(subject.splitlines())
    email = loader.render_to_string(email_template_name, c)

    return subject, email


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

    Class imitates a model functionality for use with PasswordResetSerializer
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


# pylint: disable=too-few-public-methods
class PasswordReset:
    """
    Class resets the password and sends the reset email.

    Class imitates a model functionality for use with PasswordResetSerializer
    """

    def __init__(self, email, reset_url, email_subject=None):
        self.email = email
        self.reset_url = reset_url
        self.email_subject = email_subject

    # pylint: disable=unused-argument
    def save(
        self,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="api_password_reset_email.html",
        token_generator=default_token_generator,
        from_email=None,
    ):
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """
        email = self.email
        reset_url = self.reset_url
        active_users = User.objects.filter(email__iexact=email, is_active=True)

        for user in active_users:
            # Make sure that no email is sent to a user that actually has
            # a password marked as unusable
            if not user.has_usable_password():
                continue
            subject, email = get_password_reset_email(
                user,
                reset_url,
                subject_template_name,
                email_template_name,
                email_subject=self.email_subject,
            )

            send_mail(subject, email, from_email, [user.email])


# pylint: disable=abstract-method
class PasswordResetSerializer(serializers.Serializer):
    """
    Password reset serializer.
    """

    email = serializers.EmailField(label=_("Email"), max_length=254)
    reset_url = serializers.URLField(label=_("Reset URL"), max_length=254)
    email_subject = serializers.CharField(
        label=_("Email Subject"), required=False, max_length=78, allow_blank=True
    )

    def validate_email(self, value):
        """
        Validates the email.
        """
        users = User.objects.filter(email__iexact=value)

        if users.count() == 0:
            raise serializers.ValidationError(_(f"User '{value}' does not exist."))

        return value

    def validate_email_subject(self, value):
        """
        Validate the email subject is not empty.
        """
        if value:
            return None

        return value

    def create(self, validated_data):
        """Reset a user password."""
        instance = PasswordReset(**validated_data)
        instance.save()

        return instance


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
