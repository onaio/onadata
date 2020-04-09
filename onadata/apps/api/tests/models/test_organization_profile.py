from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.team import Team
from django.db import IntegrityError
from django.test import override_settings
from django.core.cache import cache
from onadata.libs.utils.cache_tools import (
    IS_ORG, ORG_AVATAR_CACHE, safe_delete)
from onadata.libs.permissions import OwnerRole


class TestOrganizationProfile(TestBase):

    def test_create_organization_creates_team_and_perms(self):
        # create a user - bob
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        self.assertIsInstance(profile, OrganizationProfile)
        organization_profile = OrganizationProfile.objects.get(
            user__username="modilabs")

        # check organization was created
        self.assertTrue(organization_profile.is_organization)

        self.assertTrue(hasattr(profile, 'metadata'))

        # check that the default team was created
        team_name = "modilabs#%s" % Team.OWNER_TEAM_NAME
        team = Team.objects.get(
            organization=organization_profile.user, name=team_name)
        self.assertIsInstance(team, Team)
        self.assertIn(team.group_ptr, self.user.groups.all())
        self.assertTrue(self.user.has_perm('api.is_org_owner'))

        # Assert that the user has the OwnerRole for the Organization
        self.assertTrue(
            OwnerRole.user_has_role(self.user, organization_profile))

    def test_disallow_same_username_with_different_cases(self):
        tools.create_organization("modilabs", self.user)
        with self.assertRaises(IntegrityError):
            tools.create_organization("ModiLabs", self.user)

        # test disallow org create with same username same cases
        with self.assertRaises(IntegrityError):
            tools.create_organization("modiLabs", self.user)

    def test_delete_organization(self):
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        profile_id = profile.pk
        count = OrganizationProfile.objects.all().count()
        cache.set('{}{}'.format(IS_ORG, profile_id), True)

        profile.delete()
        safe_delete('{}{}'.format(IS_ORG, profile_id))
        self.assertIsNone(cache.get('{}{}'.format(IS_ORG, profile_id)))
        self.assertEqual(count - 1,
                         OrganizationProfile.objects.all().count())

    @override_settings(ORG_ON_CREATE_IS_ACTIVE=False)
    def test_optional_organization_active_status(self):
        """
        Test that setting ORG_ON_CREATE_IS_ACTIVE
        changes the default Organization is_active status
        """
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()

        self.assertFalse(profile.user.is_active)
    
    def test_cached_org_avatar(self):
        """
        Test that avatar url is set to cache
        after being updated
        """
        profile = tools.create_organization_object("modilabs", self.user)

        # clear cache
        cache.delete('{}{}'.format(profile.user, ORG_AVATAR_CACHE))

        self.assertIsNone(cache.get('{}{}'.format(profile.user, ORG_AVATAR_CACHE)))

        avatar_url = 'http://test.images.io/image/ffdc3526ba647278c7d4f3/test.png'
        profile.metadata['avatar-url'] = avatar_url
        profile.save()
        # check avatar url is saved in cache
        self.assertEqual(cache.get('{}{}'.format(profile.user, ORG_AVATAR_CACHE)), avatar_url)

