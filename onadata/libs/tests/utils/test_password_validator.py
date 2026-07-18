from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

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

    def test_history_limit_applies_to_most_recent_passwords(self):
        """Validator checks the most recently changed passwords, not the oldest

        With more history entries than the history limit, the limit must
        keep the most recent entries (ordered by changed_at descending) so
        that only passwords older than the window are allowed again.
        """
        user = User.objects.create(username="testuser")
        user.set_password("currentpassword")
        user.save()

        # Insert history oldest-first so that an unordered queryset slice
        # (which follows insertion/pk order) would wrongly keep the oldest
        # entries instead of the most recent ones.
        now = timezone.now()
        for age_in_days, raw_password in [
            (3, "oldestpass"),
            (2, "middlepass"),
            (1, "newestpass"),
        ]:
            entry = PasswordHistory.objects.create(
                user=user, hashed_password=make_password(raw_password)
            )
            # changed_at is auto_now_add, so it must be set via update()
            PasswordHistory.objects.filter(pk=entry.pk).update(
                changed_at=now - timedelta(days=age_in_days)
            )

        validator = PreviousPasswordValidator(history_limt=2)

        # The two most recently used passwords are within the window
        with self.assertRaises(ValidationError):
            validator.validate("newestpass", user=user)
        with self.assertRaises(ValidationError):
            validator.validate("middlepass", user=user)

        # The oldest password falls outside the history window
        try:
            validator.validate("oldestpass", user=user)
        except ValidationError:
            self.fail(
                "Password older than the history limit should be allowed again"
            )
