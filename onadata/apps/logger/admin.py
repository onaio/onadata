# -*- coding: utf-8 -*-
"""
Logger admin module.
"""
from django.contrib import admin

from reversion.admin import VersionAdmin

from onadata.apps.logger.models import Project, XForm


class FilterByUserMixin:  # pylint: disable=too-few-public-methods
    """Filter queryset by ``request.user``."""

    # A user should only see forms/projects that belong to him.
    def get_queryset(self, request):
        """Returns queryset filtered by the `request.user`."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(**{self.user_lookup_field: request.user})


class XFormAdmin(FilterByUserMixin, VersionAdmin, admin.ModelAdmin):
    """Customise the XForm admin view."""

    exclude = ("user",)
    list_display = ("id_string", "downloadable", "shared")
    search_fields = ("id_string", "title")
    user_lookup_field = "user"


admin.site.register(XForm, XFormAdmin)


class ProjectAdmin(FilterByUserMixin, VersionAdmin, admin.ModelAdmin):
    """Customise the Project admin view."""

    list_max_show_all = 2000
    list_select_related = ("organization",)
    ordering = ["name"]
    search_fields = ("name", "organization__username", "organization__email")
    user_lookup_field = "organization"


admin.site.register(Project, ProjectAdmin)
