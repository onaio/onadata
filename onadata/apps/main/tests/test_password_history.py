"""
Test PasswordHistory model
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import Client

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
