from django.contrib.auth.models import User


def set_api_permissions(sender, instance=None, created=False, **kwargs):
    from utils.user_auth import set_api_permissions_for_user
    if created:
        set_api_permissions_for_user(instance)
