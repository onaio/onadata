# -*- coding=utf-8 -*-
"""
UserProfile
"""
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from guardian.shortcuts import assign_perm, get_perms_for_model
from rest_framework.authtoken.models import Token

from onadata.apps.main.signals import set_api_permissions
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.gravatar import get_gravatar_img_link, gravatar_exists


class UserProfile(models.Model):
    """
    User profile info.
    """
    # This field is required.
    user = models.OneToOneField(User, related_name='profile')

    # Other fields here
    name = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=2, choices=COUNTRIES, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    home_page = models.CharField(max_length=255, blank=True)
    twitter = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    require_auth = models.BooleanField(
        default=False,
        verbose_name=ugettext_lazy("Require Phone Authentication"))
    address = models.CharField(max_length=255, blank=True)
    phonenumber = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True)
    num_of_submissions = models.IntegerField(default=0)
    metadata = JSONField(default=dict, blank=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u'%s[%s]' % (self.name, self.user.username)

    @property
    def gravatar(self):
        """
        Get user gravatar profile image link.
        """
        return get_gravatar_img_link(self.user)

    @property
    def gravatar_exists(self):
        """
        Check if a user has a profile image.
        """
        return gravatar_exists(self.user)

    @property
    def twitter_clean(self):
        """
        Return twitter username.
        """
        if self.twitter.startswith("@"):
            return self.twitter[1:]
        return self.twitter

    class Meta:
        app_label = 'main'
        permissions = (('can_add_xform',
                        "Can add/upload an xform to user profile"),
                       ('view_profile', "Can view user profile"), )


# pylint: disable=unused-argument
def create_auth_token(sender, instance=None, created=False, **kwargs):
    """
    Create authentication token for a new user profile.
    """
    if created:
        Token.objects.create(user=instance)


# pylint: disable=unused-argument
def set_object_permissions(sender, instance=None, created=False, **kwargs):
    """
    Set default UserProfile model permissions to the user and creator.
    """
    if created:
        for perm in get_perms_for_model(UserProfile):
            assign_perm(perm.codename, instance.user, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


# pylint: disable=unused-argument
def set_kpi_formbuilder_permissions(sender,
                                    instance=None,
                                    created=False,
                                    **kwargs):
    """
    Set default kpi form builder permissions to a new user profile.
    """
    if created:
        kpi_formbuilder_url = hasattr(settings, 'KPI_FORMBUILDER_URL') and\
            settings.KPI_FORMBUILDER_URL
        if kpi_formbuilder_url:
            requests.post(
                "%s/%s" % (kpi_formbuilder_url,
                           'grant-default-model-level-perms'),
                headers={
                    'Authorization': 'Token %s' % instance.user.auth_token
                })


post_save.connect(create_auth_token, sender=User, dispatch_uid='auth_token')

post_save.connect(
    set_api_permissions, sender=User, dispatch_uid='set_api_permissions')

post_save.connect(
    set_object_permissions,
    sender=UserProfile,
    dispatch_uid='set_object_permissions')

post_save.connect(
    set_kpi_formbuilder_permissions,
    sender=UserProfile,
    dispatch_uid='set_kpi_formbuilder_permission')


class UserProfileUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(UserProfile)

    def __unicode__(self):
        return u'%s[%s]' % (self.user.username, self.permission.codename)


class UserProfileGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(UserProfile)

    def __unicode__(self):
        return u'%s[%s]' % (self.group.name, self.permission.codename)
