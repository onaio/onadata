from guardian.shortcuts import get_users_with_perms

from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import (
    ManagerRole, CAN_ADD_XFORM_TO_PROFILE, ReadOnlyRole, OwnerRole, EditorRole)


def perms_for(user, obj):
    return get_users_with_perms(obj, attach_perms=True).get(user) or []


class TestPermissions(TestBase):
    def test_manager_role_add(self):
        bob = UserProfile.objects.create(user=self.user)
        alice = self._create_user('alice', 'alice')
        self.assertFalse(alice.has_perm(CAN_ADD_XFORM_TO_PROFILE, bob))

        ManagerRole.add(alice, bob)

        self.assertTrue(alice.has_perm(CAN_ADD_XFORM_TO_PROFILE, bob))

    def test_manager_has_role(self):
        bob = UserProfile.objects.create(user=self.user)
        alice = self._create_user('alice', 'alice')

        self.assertFalse(ManagerRole.user_has_role(alice, bob))
        self.assertFalse(ManagerRole.has_role(
            perms_for(alice, bob), bob))

        ManagerRole.add(alice, bob)

        self.assertTrue(ManagerRole.user_has_role(alice, bob))
        self.assertTrue(ManagerRole.has_role(
            perms_for(alice, bob), bob))

    def test_reassign_role(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(ManagerRole.user_has_role(alice, self.xform))

        ManagerRole.add(alice, self.xform)

        self.assertTrue(ManagerRole.user_has_role(alice, self.xform))
        self.assertTrue(ManagerRole.has_role(
            perms_for(alice, self.xform), self.xform))

        ReadOnlyRole.add(alice, self.xform)

        self.assertFalse(ManagerRole.user_has_role(alice, self.xform))
        self.assertTrue(ReadOnlyRole.user_has_role(alice, self.xform))
        self.assertFalse(ManagerRole.has_role(
            perms_for(alice, self.xform), self.xform))
        self.assertTrue(ReadOnlyRole.has_role(
            perms_for(alice, self.xform), self.xform))

    def test_reassign_role_owner_to_editor(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))

        OwnerRole.add(alice, self.xform)

        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))
        self.assertTrue(OwnerRole.has_role(
            perms_for(alice, self.xform), self.xform))

        EditorRole.add(alice, self.xform)

        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))
        self.assertTrue(EditorRole.user_has_role(alice, self.xform))
        self.assertFalse(OwnerRole.has_role(
            perms_for(alice, self.xform), self.xform))
        self.assertTrue(EditorRole.has_role(
            perms_for(alice, self.xform), self.xform))
