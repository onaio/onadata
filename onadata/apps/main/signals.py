from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from onadata.libs.utils.email import send_generic_email


def set_api_permissions(sender, instance=None, created=False, **kwargs):
    from onadata.libs.utils.user_auth import set_api_permissions_for_user
    if created:
        set_api_permissions_for_user(instance)


def set_user_default_project(
        sender=None, instance=None, created=False, **_):
    """ Create a default project for the user if one doesn't exist. """
    from onadata.libs.utils.user_auth import get_user_default_project
    if created:
        get_user_default_project(instance.user)


def send_inactive_user_email(
        sender, instance=None, created=False, **kwargs):
    if (created and not instance.is_active) and getattr(
            settings, "ENABLE_ACCOUNT_ACTIVATION_EMAILS", False):
        deployment_name = getattr(settings, 'DEPLOYMENT_NAME', 'Ona')
        context = {
            'username': instance.username,
            'deployment_name': deployment_name
        }
        email = render_to_string(
            'registration/inactive_account_email.txt', context)

        if instance.email:
            send_generic_email(
                instance.email,
                email,
                f'{deployment_name} account created - Pending activation')


def send_activation_email(
    sender, instance=None, **kwargs
):
    instance_id = instance.id
    if instance_id and getattr(
            settings, "ENABLE_ACCOUNT_ACTIVATION_EMAILS", False):
        try:
            user = User.objects.using('default').get(
                id=instance_id)
        except User.DoesNotExist:
            pass
        else:
            if not user.is_active and instance.is_active:
                deployment_name = getattr(settings, 'DEPLOYMENT_NAME', 'Ona')
                context = {
                    'username': instance.username,
                    'deployment_name': deployment_name
                }
                email = render_to_string(
                    'registration/activated_account_email.txt', context
                )

                if instance.email:
                    send_generic_email(
                        instance.email,
                        email,
                        f'{deployment_name} account activated'
                    )
