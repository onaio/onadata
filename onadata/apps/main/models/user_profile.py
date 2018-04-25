# -*- coding: utf-8 -*-
"""
UserProfile model class
"""
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy
from django.utils.encoding import python_2_unicode_compatible
from guardian.shortcuts import get_perms_for_model, assign_perm
from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase
from rest_framework.authtoken.models import Token
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.gravatar import get_gravatar_img_link, gravatar_exists
from onadata.apps.main.signals import set_api_permissions

REQUIRE_AUTHENTICATION = 'REQUIRE_ODK_AUTHENTICATION'


@python_2_unicode_compatible
class UserProfile(models.Model):
    """
    Userprofile model
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

    def __str__(self):
        return u'%s[%s]' % (self.name, self.user.username)

    @property
    def gravatar(self):
        return get_gravatar_img_link(self.user)

    @property
    def gravatar_exists(self):
        return gravatar_exists(self.user)

    @property
    def twitter_clean(self):
        if self.twitter.startswith("@"):
            return self.twitter[1:]
        return self.twitter

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        # Override default save method to set settings configured require_auth
        # value
        if self.pk is None and hasattr(settings, REQUIRE_AUTHENTICATION):
            self.require_auth = getattr(settings, REQUIRE_AUTHENTICATION)

        super(UserProfile, self).save(force_insert, force_update, using,
                                      update_fields)

    class Meta:
        app_label = 'main'
        permissions = (
            ('can_add_project', "Can add a project to an organization"),
            ('can_add_xform', "Can add/upload an xform to user profile"),
            ('view_profile', "Can view user profile"),
        )


def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(UserProfile):
            assign_perm(perm.codename, instance.user, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)


def set_kpi_formbuilder_permissions(
        sender, instance=None, created=False, **kwargs):
    if created:
        kpi_formbuilder_url = hasattr(settings, 'KPI_FORMBUILDER_URL') and\
            settings.KPI_FORMBUILDER_URL
        if kpi_formbuilder_url:
            requests.post(
                "%s/%s" % (
                    kpi_formbuilder_url,
                    'grant-default-model-level-perms'
                ),
                headers={
                    'Authorization': 'Token %s' % instance.user.auth_token
                }
            )


post_save.connect(create_auth_token, sender=User, dispatch_uid='auth_token')

post_save.connect(set_api_permissions, sender=User,
                  dispatch_uid='set_api_permissions')

post_save.connect(set_object_permissions, sender=UserProfile,
                  dispatch_uid='set_object_permissions')

post_save.connect(set_kpi_formbuilder_permissions, sender=UserProfile,
                  dispatch_uid='set_kpi_formbuilder_permission')


class UserProfileUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(UserProfile)


class UserProfileGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""
    content_object = models.ForeignKey(UserProfile)
