# -*- coding: utf-8 -*-
"""
Logger admin module.
"""

from django.contrib import admin, messages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.translation import gettext_lazy as _

from reversion.admin import VersionAdmin

from onadata.apps.logger.models import Project, XForm


class FilterByUserMixin:  # pylint: disable=too-few-public-methods
    """Filter queryset by ``request.user``."""

    # A user should only see forms/projects that belong to them.
    def get_queryset(self, request):
        """Returns queryset filtered by the `request.user`."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(**{self.user_lookup_field: request.user})


class XFormAdmin(FilterByUserMixin, admin.ModelAdmin):
    """Customise the XForm admin view."""

    exclude = ("user",)
    list_display = ("internal_id", "id_string", "project_id", "downloadable", "shared")
    search_fields = ("id", "id_string", "title", "project__id", "project__name")
    user_lookup_field = "user"
    actions = ["restore_form"]

    def internal_id(self, obj):
        """Display the internal ID."""
        return obj.id

    internal_id.short_description = "Internal ID"  # Label for the admin column

    def restore_form(self, request, queryset):
        """Custom admin action to restore soft-deleted XForms."""
        restored_count = 0

        for xform in queryset.iterator(chunk_size=100):
            if xform.deleted_at is not None:
                try:
                    call_command("restore_form", xform.id)
                    restored_count += 1
                except CommandError as exc:
                    self.message_user(
                        request,
                        _(f"Failed to restore XForm {xform.id_string}: {exc}"),
                        level=messages.ERROR,
                    )

        if restored_count > 0:
            self.message_user(
                request,
                _(f"Successfully restored {restored_count} XForms."),
                level=messages.SUCCESS,
            )

    restore_form.short_description = _("Restore selected deleted XForms")

    def delete_queryset(self, request, queryset):
        """
        Override delete_queryset to perform soft deletion on XForms.
        """
        for xform in queryset.iterator(chunk_size=100):
            if xform.deleted_at is None:
                xform.soft_delete(user=request.user)

    def delete_model(self, request, obj):
        """
        Override delete_model to perform soft deletion on a single XForm.
        """
        if obj.deleted_at is None:
            obj.soft_delete(user=request.user)


admin.site.register(XForm, XFormAdmin)


class ProjectAdmin(FilterByUserMixin, VersionAdmin, admin.ModelAdmin):
    """Customise the Project admin view."""

    list_max_show_all = 2000
    list_select_related = ("organization",)
    ordering = ["name"]
    search_fields = ("name", "organization__username", "organization__email")
    user_lookup_field = "organization"


admin.site.register(Project, ProjectAdmin)
