from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.validators import ValidationError
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from urlparse import urlparse


def get_user_from_uid(uid):
    try:
        uid = urlsafe_base64_decode(uid)
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        raise ValueError(_(u"Invalid uid %s") % uid)

    return user


class PasswordResetChange(object):
    def __init__(self, uid, new_password, token):
        self.uid = uid
        self.new_password = new_password
        self.token = token

    def save(self):
        user = get_user_from_uid(self.uid)
        if user:
            user.set_password(self.new_password)
            user.save()


class PasswordReset(object):
    def __init__(self, email, reset_url):
        self.email = email
        self.reset_url = reset_url

    def save(self,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='api_password_reset_email.html',
             token_generator=default_token_generator,
             from_email=None):
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
            result = urlparse(reset_url)
            site_name = domain = result.hostname
            c = {
                'email': user.email,
                'domain': domain,
                'path': result.path,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': result.scheme if result.scheme != '' else 'http',
            }
            subject = loader.render_to_string(subject_template_name, c)
            # Email subject *must not* contain newlines
            subject = ''.join(subject.splitlines())
            email = loader.render_to_string(email_template_name, c)
            send_mail(subject, email, from_email, [user.email])


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(label=_("Email"), max_length=254)
    reset_url = serializers.URLField(label=_("Reset URL"), max_length=254)

    def validate_email(self, attrs, source):
        value = attrs[source]
        users = User.objects.filter(email__iexact=value)

        if users.count() == 0:
            raise ValidationError(_(u"User '%(value)s' does not exist.")
                                  % {"value": value})

        return attrs

    def restore_object(self, attrs, instance=None):
        return PasswordReset(**attrs)


class PasswordResetChangeSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=50)
    new_password = serializers.CharField(min_length=4, max_length=128)
    token = serializers.CharField(max_length=128)

    def validate_uid(self, attrs, source):
        get_user_from_uid(attrs['uid'])

        return attrs

    def validate_token(self, attrs, source, *args, **kwargs):
        user = get_user_from_uid(attrs.get('uid'))
        value = attrs[source]

        if not default_token_generator.check_token(user, value):
            raise ValueError(_("Invalid token: %s") % value)

        return attrs

    def restore_object(self, attrs, instance=None):
        return PasswordResetChange(**attrs)
