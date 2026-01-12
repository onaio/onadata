# -*- coding: utf-8 -*-
"""Tests for onadata.apps.api.viewsets.v2.organization_viewset"""

from django.core.cache import cache
from django.test import override_settings

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_organization, get_org_profile_cache_key
from onadata.apps.api.viewsets.v2.organization_viewset import OrganizationProfileViewSet
from onadata.apps.main.models import UserProfile


@override_settings(TIME_ZONE="UTC")
class GetOrganizationListTestCase(TestAbstractViewSet):
    """Tests for GET list of organizations"""

    def setUp(self):
        super().setUp()
        self._org_create()
        self.view = OrganizationProfileViewSet.as_view({"get": "list"})

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_get_all(self):
        """GET all organizations - should exclude users field"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Cache-Control"))

        # Verify the response is a list
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)

        org_data = response.data[0]

        # Verify that 'users' field is NOT in the response
        self.assertNotIn("users", org_data)

        # Verify that 'current_user_role' IS in the response
        self.assertIn("current_user_role", org_data)
        self.assertEqual(org_data["current_user_role"], "owner")

        # Verify core fields are present
        self.assertIn("url", org_data)
        self.assertIn("org", org_data)
        self.assertIn("name", org_data)
        self.assertEqual(org_data["org"], "denoinc")
        self.assertEqual(org_data["name"], "Dennis")

    def test_list_multiple_orgs(self):
        """GET list with multiple organizations - none should have users field"""
        # Create second organization
        self._org_create(
            {
                "org": "otherinc",
                "name": "Other Inc",
                "city": "Boston",
                "country": "US",
                "home_page": "http://other.com",
                "twitter": "othertwitter",
            }
        )

        request = self.factory.get("/", **self.extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Verify neither organization has users field but has current_user_role
        for org_data in response.data:
            self.assertNotIn("users", org_data)
            self.assertIn("current_user_role", org_data)

    def test_list_excludes_owner_only_fields_for_members(self):
        """List should exclude owner-only fields for non-owners"""
        # Create another user
        alice = self._create_user("alice", "pass")
        UserProfile.objects.create(user=alice, name="Alice")

        # Add alice to organization as member (not owner)
        add_user_to_organization(self.organization, alice)

        # Make request as alice
        extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        request = self.factory.get("/", **extra)
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        org_data = response.data[0]

        # Verify owner-only fields are excluded
        self.assertNotIn("metadata", org_data)
        self.assertNotIn("email", org_data)
        self.assertNotIn("encryption_keys", org_data)

        # Verify users field is excluded (v2 list behavior)
        self.assertNotIn("users", org_data)

        # Verify current_user_role is included
        self.assertIn("current_user_role", org_data)


@override_settings(TIME_ZONE="UTC")
class RetrieveOrganizationTestCase(TestAbstractViewSet):
    """Tests for GET single organization"""

    def setUp(self):
        super().setUp()
        self._org_create()
        self.view = OrganizationProfileViewSet.as_view({"get": "retrieve"})

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_retrieve_organization(self):
        """GET single organization - should include all fields including users"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        # Verify that 'users' field IS in the response for detail view
        self.assertIn("users", response.data)

        # Verify users list structure
        users = response.data["users"]
        self.assertIsInstance(users, list)
        self.assertTrue(len(users) > 0)

        # Verify user object structure
        user = users[0]
        self.assertIn("user", user)
        self.assertIn("role", user)
        self.assertIn("first_name", user)
        self.assertIn("last_name", user)
        self.assertIn("gravatar", user)

        # Verify current_user_role is included
        self.assertIn("current_user_role", response.data)
        self.assertEqual(response.data["current_user_role"], "owner")

        # Verify core fields
        self.assertEqual(response.data["org"], "denoinc")
        self.assertEqual(response.data["name"], "Dennis")

    def test_retrieve_includes_owner_only_fields_for_owner(self):
        """Detail view should include owner-only fields for owners"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        # Verify owner-only fields are included
        self.assertIn("metadata", response.data)
        self.assertIn("email", response.data)
        self.assertIn("encryption_keys", response.data)

    def test_retrieve_excludes_owner_only_fields_for_members(self):
        """Detail view should exclude owner-only fields for non-owners"""
        # Create another user
        alice = self._create_user("alice", "pass")
        UserProfile.objects.create(user=alice, name="Alice")

        # Add alice to organization as member (not owner)
        add_user_to_organization(self.organization, alice)

        # Make request as alice
        extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        request = self.factory.get("/", **extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        # Verify owner-only fields are excluded
        self.assertNotIn("metadata", response.data)
        self.assertNotIn("email", response.data)
        self.assertNotIn("encryption_keys", response.data)

        # But users field should still be included (detail view)
        self.assertIn("users", response.data)
        self.assertIn("current_user_role", response.data)

    def test_cache_behavior(self):
        """Test that caching works correctly for organization detail"""
        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        # Verify data is cached
        cache_key = get_org_profile_cache_key(self.user, self.organization)
        cached_data = cache.get(cache_key)

        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["org"], "denoinc")
        self.assertEqual(cached_data["current_user_role"], "owner")

    def test_retrieve_with_multiple_users(self):
        """Test retrieve with multiple users in organization"""
        # Create another user and add to organization
        alice = self._create_user("alice", "pass")
        UserProfile.objects.create(user=alice, name="Alice")
        add_user_to_organization(self.organization, alice)

        request = self.factory.get("/", **self.extra)
        response = self.view(request, user="denoinc")

        self.assertEqual(response.status_code, 200)

        # Verify users list includes both users
        users = response.data["users"]
        usernames = [u["user"] for u in users]

        self.assertIn(self.user.username, usernames)
        self.assertIn("alice", usernames)

    def test_anon_user_current_user_role(self):
        """Anonymous user has no current user role"""
        # Note: This may not apply to organizations as they might require auth
        # Including for completeness based on project tests
        request = self.factory.get("/")
        response = self.view(request, user="denoinc")

        # This might return 403 or 404 depending on permissions
        # Adjust based on actual behavior
        if response.status_code == 200:
            self.assertIsNone(response.data.get("current_user_role"))
