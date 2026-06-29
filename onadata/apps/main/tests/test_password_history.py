"""
Test PasswordHistory model
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import Client

from onadata.apps.main.models.password_history import PasswordHistory

User = get_user_model()


class TestPasswordHistory(TestCase):
    """
    Test PasswordHistory model
    """

    def setUp(self):
        self.client = Client()

    def test_password_history(self):
        """
        Test that password history is tracking correctly
        """
        post_data = {
            "username": "password_history",
            "email": "password@history.com",
            "password1": "testpass",
            "password2": "testpass",
            "first_name": "Bob",
            "last_name": "User",
            "city": "Bobville",
            "country": "US",
            "organization": "Bob Inc.",
            "home_page": "test.onadata",
            "twitter": "boberama",
        }
        response = self.client.post("/accounts/register/", post_data)
        self.assertEqual(response.status_code, 302)

        try:
            user = User.objects.get(username="password_history")
        except User.DoesNotExist as e:
            self.fail(e)

        self.assertEqual(user.password_history.count(), 0)

        # Subsequent password changes should be tracked
        user.set_password("newpass")
        user.save()
        user.refresh_from_db()

        self.assertEqual(user.password_history.count(), 1)

    def test_password_change_survives_duplicate_history_hash(self):
        """A password re-save whose previous hash is already recorded must
        not raise IntegrityError and lock the user out.

        Django upgrades a stale password hash on login (re-hash + save). The
        pre_save handler then tries to re-record the *old* hash; if that hash
        is already in PasswordHistory the unguarded create() aborts the whole
        User.save(), so the upgraded hash never persists and every subsequent
        login repeats the failure — a permanent lockout. The handler must
        tolerate the duplicate and let the save succeed.
        """
        user = User.objects.create_user(username="relogin", password="passA")
        old_hash = user.password
        # Simulate the old hash already being recorded (a prior upgrade/record).
        PasswordHistory.objects.create(user=user, hashed_password=old_hash)

        # The password now changes (e.g. Django's hash upgrade on login); the
        # pre_save will try to re-record old_hash, which already exists.
        user.set_password("passB")
        user.save()  # must NOT raise IntegrityError

        user.refresh_from_db()
        self.assertTrue(user.check_password("passB"))
        # The duplicate must not have been inserted.
        self.assertEqual(
            PasswordHistory.objects.filter(hashed_password=old_hash).count(), 1
        )
