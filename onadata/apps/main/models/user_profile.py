from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy
from guardian.shortcuts import get_perms_for_model, assign_perm
from rest_framework.authtoken.models import Token
from jsonfield import JSONField
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.gravatar import get_gravatar_img_link, gravatar_exists
from onadata.apps.main.signals import set_api_permissions


class UserProfile(models.Model):
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
        default=True,
        verbose_name=ugettext_lazy("Require Phone Authentication"))
    address = models.CharField(max_length=255, blank=True)
    phonenumber = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True)
    num_of_submissions = models.IntegerField(default=0)
    metadata = JSONField(blank=True)

    def __unicode__(self):
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

    class Meta:
        app_label = 'main'
        permissions = (
            ('can_add_xform', "Can add/upload an xform to user profile"),
            ('view_profile', "Can view user profile"),
        )


def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
post_save.connect(create_auth_token, sender=User, dispatch_uid='auth_token')

post_save.connect(set_api_permissions, sender=User,
                  dispatch_uid='set_api_permissions')


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(UserProfile):
            assign_perm(perm.codename, instance.user, instance)

            if instance.created_by:
                assign_perm(perm.codename, instance.created_by, instance)
post_save.connect(set_object_permissions, sender=UserProfile,
                  dispatch_uid='set_object_permissions')
