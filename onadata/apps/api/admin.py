# -*- coding: utf-8 -*-
"""API Django admin amendments."""
from django.contrib import admin

from onadata.apps.api.models import Team, OrganizationProfile, TempToken


# pylint: disable=too-few-public-methods
class FilterSuperuserMixin:
    """Filter by request user and give full access to superuser."""

    def get_queryset(self, request):
        """Filter by request.user unless is_superuser."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)


class TeamAdmin(FilterSuperuserMixin, admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""


admin.site.register(Team, TeamAdmin)


class OrganizationProfileAdmin(FilterSuperuserMixin, admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""


admin.site.register(OrganizationProfile, OrganizationProfileAdmin)


class TempTokenProfileAdmin(FilterSuperuserMixin, admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""


admin.site.register(TempToken, TempTokenProfileAdmin)
