from reversion.admin import VersionAdmin

from django.contrib import admin

from onadata.apps.main.models import MetaData, UserProfile


class MetaDataAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('data_type', 'data_value', 'data_file', 'xform')
    search_fields = ('data_value', 'data_file', 'xform__id_string')

    def get_queryset(self, request):
        qs = super(MetaDataAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(MetaData, MetaDataAdmin)


class UserProfileAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('user', 'name')
    search_fields = ('name', 'user__username')

    def get_queryset(self, request):
        qs = super(UserProfileAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(UserProfile, UserProfileAdmin)
