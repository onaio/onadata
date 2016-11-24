from django.contrib import admin

from onadata.apps.api.models import Team, OrganizationProfile, TempToken


class TeamAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        qs = super(TeamAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


admin.site.register(Team, TeamAdmin)


class OrganizationProfileAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        qs = super(OrganizationProfileAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


admin.site.register(OrganizationProfile, OrganizationProfileAdmin)


class TempTokenProfileAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        qs = super(TempTokenProfileAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


admin.site.register(TempToken, TempTokenProfileAdmin)
