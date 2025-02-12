# -*- coding: utf-8 -*-
"""
UserProfile model class
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.utils.translation import gettext_lazy

import jwt
import requests
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model
from rest_framework.authtoken.models import Token

from onadata.apps.main.signals import (
    send_activation_email,
    send_inactive_user_email,
    set_api_permissions,
)
from onadata.libs.utils.common_tags import API_TOKEN, ONADATA_KOBOCAT_AUTH_HEADER
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.gravatar import get_gravatar_img_link, gravatar_exists

DEFAULT_REQUEST_TIMEOUT = getattr(settings, "DEFAULT_REQUEST_TIMEOUT", 30)

REQUIRE_AUTHENTICATION = "REQUIRE_ODK_AUTHENTICATION"

# pylint: disable=invalid-name
User = get_user_model()


class UserProfile(models.Model):
    """
    Userprofile model
    """

    # This field is required.
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)

    # Other fields here
    name = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=2, choices=COUNTRIES, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    home_page = models.CharField(max_length=255, blank=True)
    twitter = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    require_auth = models.BooleanField(
        default=False, verbose_name=gettext_lazy("Require Phone Authentication")
    )
    address = models.CharField(max_length=255, blank=True)
    phonenumber = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    num_of_submissions = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}[{self.user.username}]"

    @property
    def gravatar(self):
        """
        Returns Gravatar URL.
        """
        return get_gravatar_img_link(self.user)

    @property
    def gravatar_exists(self):
        """
        Check if Gravatar URL exists.
        """
        return gravatar_exists(self.user)

    @property
    def twitter_clean(self):
        """
        Remove the '@' from twitter name.
        """
        if self.twitter.startswith("@"):
            return self.twitter[1:]
        return self.twitter

    def save(
        self,
        *args,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        # Override default save method to set settings configured require_auth
        # value
        if self.pk is None and hasattr(settings, REQUIRE_AUTHENTICATION):
            self.require_auth = getattr(settings, REQUIRE_AUTHENTICATION)

        super().save(*args, force_insert, force_update, using, update_fields)

    class Meta:
        app_label = "main"
        permissions = (
            ("can_add_project", "Can add a project to an organization"),
            ("can_add_xform", "Can add/upload an xform to user profile"),
            ("view_profile", "Can view user profile"),
        )


# pylint: disable=unused-argument
def create_auth_token(sender, instance=None, created=False, **kwargs):
    """
    Creates an authentication Token.
    """
    if created:
        Token.objects.create(user=instance)


# pylint: disable=unused-argument
def set_object_permissions(sender, instance=None, created=False, **kwargs):
    """
    Assign's permission to the user that created the profile.
    """
    if created:
        for perm in get_perms_for_model(UserProfile):
            assign_perm(perm.codename, instance.user, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


# pylint: disable=unused-argument
def set_kpi_formbuilder_permissions(sender, instance=None, created=False, **kwargs):
    """
    Assign KPI permissions to allow the user to create forms using KPI formbuilder.
    """
    if created:
        kpi_formbuilder_url = (
            hasattr(settings, "KPI_FORMBUILDER_URL") and settings.KPI_FORMBUILDER_URL
        )
        if kpi_formbuilder_url:
            auth_header = {
                ONADATA_KOBOCAT_AUTH_HEADER: jwt.encode(
                    {API_TOKEN: instance.user.auth_token.key},
                    getattr(settings, "JWT_SECRET_KEY", "jwt"),
                    algorithm=getattr(settings, "JWT_ALGORITHM", "HS256"),
                )
            }
            requests.post(
                f"{kpi_formbuilder_url}/grant-default-model-level-perms",
                headers=auth_header,
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )


post_save.connect(create_auth_token, sender=User, dispatch_uid="auth_token")
post_save.connect(
    send_inactive_user_email, sender=User, dispatch_uid="send_inactive_user_email"
)
pre_save.connect(
    send_activation_email, sender=User, dispatch_uid="send_activation_email"
)

post_save.connect(set_api_permissions, sender=User, dispatch_uid="set_api_permissions")

post_save.connect(
    set_object_permissions, sender=UserProfile, dispatch_uid="set_object_permissions"
)

post_save.connect(
    set_kpi_formbuilder_permissions,
    sender=UserProfile,
    dispatch_uid="set_kpi_formbuilder_permission",
)


# pylint: disable=too-few-public-methods
class UserProfileUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(UserProfile, on_delete=models.CASCADE)


# pylint: disable=too-few-public-methods
class UserProfileGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
