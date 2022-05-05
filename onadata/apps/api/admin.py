# -*- coding: utf-8 -*-
"""API Django admin amendments."""
from django.contrib import admin

from onadata.apps.api.models import Team, OrganizationProfile, TempToken


class TeamAdmin(admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""

    def get_queryset(self, request):
        """Filter by request.user unless is_superuser."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)


admin.site.register(Team, TeamAdmin)


class OrganizationProfileAdmin(admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""

    def get_queryset(self, request):
        """Filter by request.user unless is_superuser."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)


admin.site.register(OrganizationProfile, OrganizationProfileAdmin)


class TempTokenProfileAdmin(admin.ModelAdmin):
    """Filter by request.user unless is_superuser."""

    def get_queryset(self, request):
        """Filter by request.user unless is_superuser."""
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)


admin.site.register(TempToken, TempTokenProfileAdmin)
