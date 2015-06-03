from guardian.shortcuts import get_users_with_perms

from onadata.apps.api import tools
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import (
    get_object_users_with_permissions,
    ManagerRole,
    CAN_ADD_XFORM_TO_PROFILE,
    ReadOnlyRole,
    OwnerRole,
    EditorRole,
    ReadOnlyRoleNoDownload)


def perms_for(user, obj):
    return get_users_with_perms(obj, attach_perms=True).get(user) or []


class TestPermissions(TestBase):

    def test_manager_role_add(self):
        bob, created = UserProfile.objects.get_or_create(user=self.user)
        alice = self._create_user('alice', 'alice')
        self.assertFalse(alice.has_perm(CAN_ADD_XFORM_TO_PROFILE, bob))

        ManagerRole.add(alice, bob)

        self.assertTrue(alice.has_perm(CAN_ADD_XFORM_TO_PROFILE, bob))

    def test_manager_has_role(self):
        bob, created = UserProfile.objects.get_or_create(user=self.user)
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

    def test_get_object_users_with_permission(self):
        alice = self._create_user('alice', 'alice')
        org_user = tools.create_organization("modilabs", alice).user
        self._publish_transportation_form()
        EditorRole.add(org_user, self.xform)
        users_with_perms = get_object_users_with_permissions(self.xform)
        self.assertTrue(org_user in [d['user'] for d in users_with_perms])
        self.assertIn('first_name', users_with_perms[0].keys())
        self.assertIn('last_name', users_with_perms[0].keys())

    def test_readonly_no_downloads_has_role(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(ReadOnlyRoleNoDownload.user_has_role(alice,
                                                              self.xform))
        self.assertFalse(ReadOnlyRoleNoDownload.has_role(
            perms_for(alice, self.xform), self.xform))

        ReadOnlyRoleNoDownload.add(alice, self.xform)

        self.assertTrue(ReadOnlyRoleNoDownload.user_has_role(alice,
                                                             self.xform))
        self.assertTrue(ReadOnlyRoleNoDownload.has_role(
            perms_for(alice, self.xform), self.xform))
