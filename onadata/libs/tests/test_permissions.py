from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ManagerRole, CAN_ADD_XFORM_TO_PROFILE


class TestPermissions(TestBase):
    def test_manager_role_add(self):
        bob = UserProfile.objects.create(user=self.user)
        alice = self._create_user('alice', 'alice')
        ManagerRole.add(alice, bob)

        self.assertTrue(alice.has_perm(CAN_ADD_XFORM_TO_PROFILE, bob))
