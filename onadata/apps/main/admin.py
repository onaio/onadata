# -*- coding: utf-8 -*-
"""API Django admin amendments."""
# pylint: disable=imported-auth-user
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class BaseCustomUserForm:
    """
    Base form class for custom user forms.
    Contains common logic for validating the username.
    """

    def clean_username(self):
        """
        Clean the username field to ensure it does not contain hyphens.
        Raises:
            ValidationError: If the username contains hyphens.
        Returns:
            str: The cleaned username.
        """
        username = self.cleaned_data["username"]
        if "-" in username:
            raise ValidationError("Usernames cannot contain hyphens.")
        return username


class CustomUserCreationForm(BaseCustomUserForm, UserCreationForm):
    """
    Custom form for user creation.
    Inherits from BaseCustomUserForm and UserCreationForm.
    """

    class Meta(UserCreationForm.Meta):
        model = User


class CustomUserChangeForm(BaseCustomUserForm, UserChangeForm):
    """
    Custom form for user change.
    Inherits from BaseCustomUserForm and UserChangeForm.
    """

    class Meta(UserChangeForm.Meta):
        model = User


class CustomUserAdmin(UserAdmin):
    """
    Custom User admin panel configuration.
    """

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
