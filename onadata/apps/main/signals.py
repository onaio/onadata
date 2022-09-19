# -*- coding: utf-8 -*-
"""
signal module.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from onadata.libs.utils.email import send_generic_email


User = get_user_model()


# pylint: disable=unused-argument
def set_api_permissions(sender, instance=None, created=False, **kwargs):
    """Sets API permissions for a user."""
    # pylint: disable=import-outside-toplevel
    from onadata.libs.utils.user_auth import set_api_permissions_for_user

    if created:
        set_api_permissions_for_user(instance)


def send_inactive_user_email(sender, instance=None, created=False, **kwargs):
    """Sends email to inactive user upon account creation."""
    if (created and not instance.is_active) and getattr(
        settings, "ENABLE_ACCOUNT_ACTIVATION_EMAILS", False
    ):
        deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
        context = {"username": instance.username, "deployment_name": deployment_name}
        email = render_to_string("registration/inactive_account_email.txt", context)

        if instance.email:
            send_generic_email(
                instance.email,
                email,
                f"{deployment_name} account created - Pending activation",
            )


def send_activation_email(sender, instance=None, **kwargs):
    """Sends activation email to user."""
    instance_id = instance.id
    if instance_id and getattr(settings, "ENABLE_ACCOUNT_ACTIVATION_EMAILS", False):
        try:
            user = User.objects.using("default").get(id=instance_id)
        except User.DoesNotExist:
            pass
        else:
            if not user.is_active and instance.is_active:
                deployment_name = getattr(settings, "DEPLOYMENT_NAME", "Ona")
                context = {
                    "username": instance.username,
                    "deployment_name": deployment_name,
                }
                email = render_to_string(
                    "registration/activated_account_email.txt", context
                )

                if instance.email:
                    send_generic_email(
                        instance.email, email, f"{deployment_name} account activated"
                    )
