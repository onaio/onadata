from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings

import reversion
from guardian.shortcuts import get_perms, get_perms_for_model
from moto import mock_aws
from reversion import revisions
from reversion.models import Version

from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    add_user_to_team,
    is_organization_owners_team,
)
from onadata.apps.api.models.team import Team
from onadata.apps.logger.models import KMSKey
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import OwnerRole
from onadata.libs.utils.cache_tools import IS_ORG, safe_cache_delete


class TestOrganizationProfile(TestBase):
    def test_create_organization_creates_team_and_perms(self):
        # create a user - bob
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        self.assertIsInstance(profile, OrganizationProfile)
        organization_profile = OrganizationProfile.objects.get(
            user__username="modilabs"
        )

        # check organization was created
        self.assertTrue(organization_profile.is_organization)

        self.assertTrue(hasattr(profile, "metadata"))

        # check that the default team was created
        team_name = "modilabs#%s" % Team.OWNER_TEAM_NAME
        team = Team.objects.get(organization=organization_profile.user, name=team_name)
        self.assertIsInstance(team, Team)
        self.assertIn(team.group_ptr, self.user.groups.all())
        self.assertTrue(self.user.has_perm("api.is_org_owner"))

        # Assert that the user has the OwnerRole for the Organization
        self.assertTrue(OwnerRole.user_has_role(self.user, organization_profile))

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
        cache.set(f"{IS_ORG}{profile_id}", True)

        profile.delete()
        safe_cache_delete(f"{IS_ORG}{profile_id}")
        self.assertIsNone(cache.get(f"{IS_ORG}{profile_id}"))
        self.assertEqual(count - 1, OrganizationProfile.objects.all().count())

    @override_settings(ORG_ON_CREATE_IS_ACTIVE=False)
    def test_optional_organization_active_status(self):
        """
        Test that setting ORG_ON_CREATE_IS_ACTIVE
        changes the default Organization is_active status
        """
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()

        self.assertFalse(profile.user.is_active)

    @mock_aws
    @override_settings(
        KMS_PROVIDER="AWS",
        AWS_ACCESS_KEY_ID="fake-id",
        AWS_SECRET_ACCESS_KEY="fake-secret",
        AWS_KMS_REGION_NAME="us-east-1",
    )
    def test_create_kms_key(self):
        """KMSkey is created when org is created."""

        with override_settings(KMS_AUTO_CREATE_KEY=True):
            profile = tools.create_organization_object("modilabs", self.user)
            profile.save()
            content_type = ContentType.objects.get_for_model(OrganizationProfile)

            kms_key_qs = KMSKey.objects.filter(
                object_id=profile.pk, content_type=content_type
            )

            self.assertEqual(kms_key_qs.count(), 1)

            # Key is only created when org is created and not updated
            profile.save()

            self.assertEqual(kms_key_qs.all().count(), 1)

        # KMSKey auto-create disabled

        with override_settings(KMS_AUTO_CREATE_KEY=False):
            profile.delete()
            profile = tools.create_organization_object("modilabs", self.user)
            profile.save()
            content_type = ContentType.objects.get_for_model(OrganizationProfile)

            kms_key_qs = KMSKey.objects.filter(
                object_id=profile.pk, content_type=content_type
            )

            self.assertEqual(kms_key_qs.count(), 0)

        # KMSKey auto-create config missing
        profile.delete()
        profile = tools.create_organization_object("modilabs", self.user)
        profile.save()
        content_type = ContentType.objects.get_for_model(OrganizationProfile)

        kms_key_qs = KMSKey.objects.filter(
            object_id=profile.pk, content_type=content_type
        )

        self.assertEqual(kms_key_qs.count(), 0)

    def test_organization_profile_is_registered(self):
        """OrganizationProfile is registered with django-reversion."""
        self.assertTrue(reversion.is_registered(OrganizationProfile))

    def test_revision_recorded_and_read(self):
        """An OrganizationProfile saved in a revision is recorded and readable."""
        profile = OrganizationProfile.objects.create(
            user=User.objects.create(username="modilabs"),
            creator=self.user,
            name="Modi Labs",
            email="info@modilabs.org",
        )

        with revisions.create_revision():
            revisions.add_to_revision(profile)

        version = Version.objects.get_for_object(profile).first()
        self.assertIsNotNone(version)
        self.assertEqual(version.field_dict["email"], "info@modilabs.org")
        self.assertEqual(version.field_dict["name"], "Modi Labs")


class TestIsOrganizationOwnersTeam(TestBase):
    """Tests for ``is_organization_owners_team``."""

    def setUp(self):
        super().setUp()
        self.organization = self._create_organization(
            username="modilabs", name="Modi Labs", created_by=self.user
        )

    def test_only_the_canonical_owners_team_qualifies(self):
        """Only the team named ``<organization>#Owners`` is the Owners team."""
        owners_team = Team.objects.get(
            organization=self.organization.user, name="modilabs#Owners"
        )
        self.assertTrue(is_organization_owners_team(owners_team))

        for name in ["Data Owners", "Co-Owners", "xOwners"]:
            team = Team.objects.create(organization=self.organization.user, name=name)
            self.assertFalse(is_organization_owners_team(team))


class TestAddUserToTeam(TestBase):
    """Tests for ``add_user_to_team``."""

    def setUp(self):
        super().setUp()
        self.organization = self._create_organization(
            username="modilabs", name="Modi Labs", created_by=self.user
        )
        self.owners_team = Team.objects.get(
            organization=self.organization.user, name="modilabs#Owners"
        )
        self.members_team = Team.objects.create(
            organization=self.organization.user, name="members"
        )
        self.user_deno = self._create_user("deno", "deno")
        self.team_perms = sorted(perm.codename for perm in get_perms_for_model(Team))

    def test_lookalike_owners_team_grants_no_owner_perms(self):
        """Joining a team merely named like Owners grants no Owners permissions."""
        for name in ["Data Owners", "Co-Owners", "xOwners"]:
            team = Team.objects.create(organization=self.organization.user, name=name)
            add_user_to_team(team, self.user_deno)

            self.assertIn(team.group_ptr, self.user_deno.groups.all())
            self.assertEqual(get_perms(self.user_deno, self.owners_team), [])
            self.assertEqual(get_perms(self.user_deno, self.members_team), [])
            self.assertFalse(self.organization.is_organization_owner(self.user_deno))

    def test_owners_team_grants_owner_perms(self):
        """Joining the Owners team grants the Owners and members team permissions."""
        add_user_to_team(self.owners_team, self.user_deno)

        self.assertIn(self.owners_team.group_ptr, self.user_deno.groups.all())
        self.assertEqual(
            sorted(get_perms(self.user_deno, self.owners_team)), self.team_perms
        )
        self.assertEqual(
            sorted(get_perms(self.user_deno, self.members_team)), self.team_perms
        )
        self.assertTrue(self.organization.is_organization_owner(self.user_deno))
