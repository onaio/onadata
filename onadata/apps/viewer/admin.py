# -*- coding: utf-8 -*-
from reversion.admin import VersionAdmin

from django.contrib import admin

from onadata.apps.viewer.models import DataDictionary


class DataDictionaryAdmin(VersionAdmin, admin.ModelAdmin):
    exclude = ("user",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)


admin.site.register(DataDictionary, DataDictionaryAdmin)
