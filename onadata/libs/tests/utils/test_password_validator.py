from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from onadata.apps.main.models.password_history import PasswordHistory
from onadata.libs.utils.validators import PreviousPasswordValidator

class PreviousPasswordValidatorTestCase(TestCase):
    def test_validator_does_not_raise_valueerror_missing_pk(self):
        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Create a user instance without saving it to the database
        user = User(username='testuser')

        # Call the validate method and ensure it does not raise a ValueError
        try:
            validator.validate('somepassword', user=user)
        except ValueError:
            self.fail("PreviousPasswordValidator raised ValueError unexpectedly!")

    def test_validator_raises_validationerror_for_reused_password(self):
        # Create and save a user to the database
        user = User.objects.create(username='testuser')
        user.set_password('oldpassword')
        user.save()

        # Add the old password to password history
        PasswordHistory.objects.create(user=user, hashed_password=user.password)

        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Try using an old password
        with self.assertRaises(ValidationError) as cm:
            validator.validate('oldpassword', user=user)

        self.assertEqual(
            str(cm.exception.message), "You cannot use a previously used password.")

    def test_validator_allows_new_password(self):
        # Create and save a user to the database
        user = User.objects.create(username='testuser')
        user.set_password('oldpassword')
        user.save()

        # Add the old password to password history
        PasswordHistory.objects.create(user=user, hashed_password=user.password)

        # Create a validator instance
        validator = PreviousPasswordValidator()

        # Try using a new password
        try:
            validator.validate('newpassword@123', user=user)
        except ValidationError:
            self.fail("PreviousPasswordValidator raised ValidationError unexpectedly!")
