from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from onadata.apps.main.models.password_history import PasswordHistory
from onadata.libs.utils.validators import PreviousPasswordValidator


class PreviousPasswordValidatorTestCase(TestCase):
    """
    Test case for the PreviousPasswordValidator class.
    Ensures correct behavior of password validation.
    """

    def test_missing_pk(self):
        """Validator does not raise ValueError for missing pk"""
        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Create a user instance without saving it to the database
        user = User(username="testuser")

        # Call the validate method and ensure it does not raise a ValueError
        try:
            validator.validate("somepassword", user=user)
        except ValueError:
            self.fail("PreviousPasswordValidator raised ValueError unexpectedly!")

    def test_reused_password(self):
        """Test ValidationError exception thrown on reused password"""
        # Create and save a user to the database
        user = User.objects.create(username="testuser")
        user.set_password("oldpassword")
        user.save()

        # Add the old password to password history
        PasswordHistory.objects.create(user=user, hashed_password=user.password)

        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Try using an old password
        with self.assertRaises(ValidationError) as cm:
            validator.validate("oldpassword", user=user)

        self.assertEqual(
            str(cm.exception.message), "You cannot use a previously used password."
        )

    def test_allows_new_password(self):
        """Test validator allows new password not used before"""
        # Create and save a user to the database
        user = User.objects.create(username="testuser")
        user.set_password("oldpassword")
        user.save()

        # Add the old password to password history
        PasswordHistory.objects.create(user=user, hashed_password=user.password)

        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Try using a new password
        try:
            validator.validate("newpassword@123", user=user)
        except ValidationError:
            self.fail("PreviousPasswordValidator raised ValidationError unexpectedly!")
