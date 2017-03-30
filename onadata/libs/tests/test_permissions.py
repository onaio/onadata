from guardian.shortcuts import get_users_with_perms
from mock import patch

from onadata.apps.api import tools
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import (
    CAN_ADD_XFORM_TO_PROFILE, DataEntryMinorRole, EditorRole, ManagerRole,
    NoRecordsPermission, OwnerRole, ReadOnlyRole, ReadOnlyRoleNoDownload,
    filter_queryset_xform_meta_perms_sql, get_object_users_with_permissions)


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
        self.assertFalse(ManagerRole.has_role(perms_for(alice, bob), bob))

        ManagerRole.add(alice, bob)

        self.assertTrue(ManagerRole.user_has_role(alice, bob))
        self.assertTrue(ManagerRole.has_role(perms_for(alice, bob), bob))

    def test_reassign_role(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(ManagerRole.user_has_role(alice, self.xform))

        ManagerRole.add(alice, self.xform)

        self.assertTrue(ManagerRole.user_has_role(alice, self.xform))
        self.assertTrue(
            ManagerRole.has_role(perms_for(alice, self.xform), self.xform))

        ReadOnlyRole.add(alice, self.xform)

        self.assertFalse(ManagerRole.user_has_role(alice, self.xform))
        self.assertTrue(ReadOnlyRole.user_has_role(alice, self.xform))
        self.assertFalse(
            ManagerRole.has_role(perms_for(alice, self.xform), self.xform))
        self.assertTrue(
            ReadOnlyRole.has_role(perms_for(alice, self.xform), self.xform))

    def test_reassign_role_owner_to_editor(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))

        OwnerRole.add(alice, self.xform)

        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))
        self.assertTrue(
            OwnerRole.has_role(perms_for(alice, self.xform), self.xform))

        EditorRole.add(alice, self.xform)

        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))
        self.assertTrue(EditorRole.user_has_role(alice, self.xform))
        self.assertFalse(
            OwnerRole.has_role(perms_for(alice, self.xform), self.xform))
        self.assertTrue(
            EditorRole.has_role(perms_for(alice, self.xform), self.xform))

    def test_get_object_users_with_permission(self):
        alice = self._create_user('alice', 'alice')
        org_user = tools.create_organization("modilabs", alice).user
        self._publish_transportation_form()
        EditorRole.add(org_user, self.xform)
        users_with_perms = get_object_users_with_permissions(self.xform)
        self.assertTrue(org_user in [d['user'] for d in users_with_perms])
        self.assertIn('first_name', users_with_perms[0].keys())
        self.assertIn('last_name', users_with_perms[0].keys())
        self.assertIn('user', users_with_perms[0].keys())
        self.assertIn('role', users_with_perms[0].keys())
        self.assertIn('gravatar', users_with_perms[0].keys())
        self.assertIn('metadata', users_with_perms[0].keys())
        self.assertIn('is_org', users_with_perms[0].keys())

    def test_readonly_no_downloads_has_role(self):
        self._publish_transportation_form()
        alice = self._create_user('alice', 'alice')

        self.assertFalse(
            ReadOnlyRoleNoDownload.user_has_role(alice, self.xform))
        self.assertFalse(
            ReadOnlyRoleNoDownload.has_role(
                perms_for(alice, self.xform), self.xform))

        ReadOnlyRoleNoDownload.add(alice, self.xform)

        self.assertTrue(
            ReadOnlyRoleNoDownload.user_has_role(alice, self.xform))
        self.assertTrue(
            ReadOnlyRoleNoDownload.has_role(
                perms_for(alice, self.xform), self.xform))

    @patch('onadata.libs.permissions._check_meta_perms_enabled')
    def test_filter_queryset_xform_meta_perms_sql(self, check_meta_mock):
        self._publish_transportation_form()

        query = '{"_id": 1}'
        result = filter_queryset_xform_meta_perms_sql(self.xform, self.user,
                                                      query)
        self.assertEqual(result, query)

        check_meta_mock.return_value = True
        alice = self._create_user('alice', 'alice')

        # no records
        with self.assertRaises(NoRecordsPermission):
            filter_queryset_xform_meta_perms_sql(self.xform, alice, query)

        DataEntryMinorRole.add(alice, self.xform)

        # meta perms test
        result = filter_queryset_xform_meta_perms_sql(self.xform, alice, query)
        self.assertEqual(result, '{"_submitted_by": "alice", "_id": 1}')

        query = '[{"_id": 1}]'
        result = filter_queryset_xform_meta_perms_sql(self.xform, alice, query)
        self.assertEqual(result, '{"_submitted_by": "alice", "_id": 1}')

        result = filter_queryset_xform_meta_perms_sql(self.xform, alice, None)
        self.assertEqual(result, '{"_submitted_by": "alice"}')
