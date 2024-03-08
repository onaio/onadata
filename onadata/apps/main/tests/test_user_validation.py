from onadata.apps.main.admin import CustomUserChangeForm, CustomUserCreationForm
from onadata.apps.main.tests.test_base import TestBase


class TestUserValidation(TestBase):
    def test_custom_user_creation_form_invalid_username(self):
        # Try to create a user with a hyphenated username
        form_data = {
            "username": "john-doe",
            "password1": "testpassword",
            "password2": "testpassword",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        errors = form.errors.get("username")[0]
        self.assertEqual(str(errors), "Usernames cannot contain hyphens.")

    def test_custom_user_change_form_invalid_username(self):
        # Try to change a user's username to one with a hyphen
        user = self._create_user("bob-user", "bob")
        form_data = {"username": "bob-user-1"}
        form = CustomUserChangeForm(data=form_data, instance=user)
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        errors = form.errors.get("username")[0]
        self.assertEqual(str(errors), "Usernames cannot contain hyphens.")
