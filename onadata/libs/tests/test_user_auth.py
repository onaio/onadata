# -*- coding: utf-8 -*-
"""
Tests onadata.libs.utils.user_auth module
"""

from django.contrib.auth.models import User

from guardian.shortcuts import assign_perm

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.user_auth import get_xform_users_with_perms


class TestGetXformUsersWithPerms(TestBase):
    """
    Tests for get_xform_users_with_perms function
    """

    def test_single_permission(self):
        """
        Test that a user with a single permission is returned correctly.
        """
        self._publish_transportation_form()
        alice = self._create_user("alice", "alice")

        assign_perm("view_xform", alice, self.xform)

        user_perms = get_xform_users_with_perms(self.xform)

        self.assertIn(alice, user_perms)
        self.assertEqual(user_perms[alice], ["view_xform"])

    def test_multiple_permissions_same_user(self):
        """
        Test that a user with multiple permissions returns ALL permissions.
        This test would have failed with the bug where p.user.username was
        checked instead of p.user as dictionary key.
        """
        self._publish_transportation_form()
        alice = self._create_user("alice", "alice")

        assign_perm("view_xform", alice, self.xform)
        assign_perm("change_xform", alice, self.xform)
        assign_perm("delete_xform", alice, self.xform)

        user_perms = get_xform_users_with_perms(self.xform)

        self.assertIn(alice, user_perms)
        self.assertEqual(len(user_perms[alice]), 3)
        self.assertIn("view_xform", user_perms[alice])
        self.assertIn("change_xform", user_perms[alice])
        self.assertIn("delete_xform", user_perms[alice])

    def test_multiple_users_with_permissions(self):
        """
        Test that multiple users with different permissions are returned correctly.
        """
        self._publish_transportation_form()
        alice = self._create_user("alice", "alice")
        charlie = self._create_user("charlie", "charlie")

        assign_perm("view_xform", alice, self.xform)
        assign_perm("change_xform", alice, self.xform)
        assign_perm("view_xform", charlie, self.xform)

        user_perms = get_xform_users_with_perms(self.xform)

        self.assertEqual(len(user_perms), 3)
        self.assertIn(alice, user_perms)
        self.assertIn(charlie, user_perms)
        self.assertEqual(len(user_perms[alice]), 2)
        self.assertIn("view_xform", user_perms[alice])
        self.assertIn("change_xform", user_perms[alice])
        self.assertEqual(user_perms[charlie], ["view_xform"])

    def test_no_permissions(self):
        """
        Test that an empty dict is returned when no permissions are assigned.
        """
        self._publish_transportation_form()

        user_perms = get_xform_users_with_perms(self.xform)
        del user_perms[User.objects.get(username="bob")]

        self.assertEqual(
            user_perms,
            {},
        )

    def test_user_key_is_user_object_not_username(self):
        """
        Test that the dictionary keys are User objects, not username strings.
        """
        self._publish_transportation_form()
        alice = self._create_user("alice", "alice")

        assign_perm("view_xform", alice, self.xform)

        user_perms = get_xform_users_with_perms(self.xform)

        # Keys should be User objects
        for key in user_perms.keys():
            self.assertNotIsInstance(key, str)
            self.assertEqual(key.__class__.__name__, "User")
