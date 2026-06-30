# -*- coding: utf-8 -*-
"""Main Django admin registrations."""

from django.apps import apps
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from onadata.apps.main.models import UserDeactivationState
from onadata.apps.main.models.user_deactivation import reactivate_user


class UserDeactivationStateAdmin(admin.ModelAdmin):
    """Admin for inactive-account lifecycle state."""

    actions = ["reactivate_selected_users"]
    list_display = (
        "username",
        "email",
        "deactivation_scheduled_at",
        "deactivated_at",
        "reactivated_at",
        "permission_policy_applied",
    )
    list_filter = ("permission_policy_applied", "deactivated_at", "reactivated_at")
    list_select_related = ("user",)
    ordering = ("user__username",)
    readonly_fields = (
        "date_created",
        "date_modified",
        "deactivated_at",
        "reactivated_at",
        "permissions_revoked_at",
        "permission_policy_applied",
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )

    def username(self, obj):
        """Display the username."""
        return obj.user.username

    username.admin_order_field = "user__username"

    def email(self, obj):
        """Display the user email."""
        return obj.user.email

    email.admin_order_field = "user__email"

    def reactivate_selected_users(self, request, queryset):
        """Reactivate selected users currently disabled by lifecycle processing."""
        when = timezone.now()
        reactivated_count = 0
        skipped_count = 0

        for state in queryset.select_related("user").iterator(chunk_size=100):
            result = reactivate_user(state, when=when)
            if result.reactivated:
                reactivated_count += 1
            else:
                skipped_count += 1

        if reactivated_count:
            self.message_user(
                request,
                _(f"Reactivated {reactivated_count} inactive users."),
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                _(
                    f"Skipped {skipped_count} users that were not currently deactivated."
                ),
                level=messages.WARNING,
            )

    reactivate_selected_users.short_description = _(
        "Reactivate selected inactive-account users"
    )


if apps.is_installed("django.contrib.admin"):
    admin.site.register(UserDeactivationState, UserDeactivationStateAdmin)
