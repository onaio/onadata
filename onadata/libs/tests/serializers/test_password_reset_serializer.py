from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.main.models import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.serializers.password_reset_serializer import (
    PasswordReset,
    get_password_reset_email,
)

User = get_user_model()


class TestPasswordResetSerializer(TestBase):
    def test_get_password_reset_email(self):
        """Test base64 username is included in reset email."""
        _, email = get_password_reset_email(self.user, "https://ona.io")

        self.assertIn(
            urlsafe_base64_encode(self.user.username.encode("utf-8")),
            email,
            "Username is included in reset email.",
        )
        self.assertIn(
            "uid={}".format(urlsafe_base64_encode(force_bytes(self.user.pk))),
            email,
            "Uid is included in email.",
        )

    def test_password_reset_excludes_organizations(self):
        """Test that password reset excludes organization profiles."""
        org_user = User.objects.create_user(
            username="testorg", email="test@example.com"
        )
        org_user.is_active = True
        org_user.save()
        org_owner = User.objects.get(username="bob")
        OrganizationProfile.objects.create(
            creator=org_owner, user=org_user, name="Test Organization"
        )

        regular_user = User.objects.create_user(
            username="regularuser", email="test@example.com", password="testpass123"
        )
        regular_user.is_active = True
        regular_user.save()
        UserProfile.objects.create(user=regular_user)

        password_reset = PasswordReset(
            email="test@example.com", reset_url="https://ona.io/reset"
        )

        with patch(
            "onadata.libs.serializers.password_reset_serializer.send_mail"
        ) as mock_send_mail:
            password_reset.save()
            mock_send_mail.assert_called_once()
            args = mock_send_mail.call_args[0]
            self.assertEqual(args[3], [regular_user.email])

    def test_password_reset_only_active_users(self):
        """Test that password reset only considers active Users."""
        inactive_user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="testpass123",
        )
        inactive_user.is_active = False
        inactive_user.save()
        UserProfile.objects.create(user=inactive_user)

        password_reset = PasswordReset(
            email="inactive@example.com", reset_url="https://ona.io/reset"
        )

        with patch(
            "onadata.libs.serializers.password_reset_serializer.send_mail"
        ) as mock_send_mail:
            password_reset.save()
            mock_send_mail.assert_not_called()
