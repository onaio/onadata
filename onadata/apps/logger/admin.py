from reversion.admin import VersionAdmin

from django.contrib import admin

from onadata.apps.logger.models import XForm, Project, SurveyType, Instance


class InstanceAdmin(VersionAdmin, admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('uuid', 'xform')
    search_fields = ('uuid', 'xform__id_string')

    def get_queryset(self, request):
        qs = super(InstanceAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Instance, InstanceAdmin)


class XFormAdmin(VersionAdmin, admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('id_string', 'downloadable', 'shared')
    search_fields = ('id_string', 'title')

    # A user should only see forms that belong to him.
    def get_queryset(self, request):
        qs = super(XFormAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(XForm, XFormAdmin)


class ProjectAdmin(VersionAdmin, admin.ModelAdmin):
    list_max_show_all = 2000
    list_select_related = ('organization',)
    ordering = ['name']
    search_fields = ('name', 'organization__username', 'organization__email')

    # A user should only see projects that belong to him.
    def get_queryset(self, request):
        qs = super(ProjectAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Project, ProjectAdmin)


class SurveyTypeAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('slug',)

    def get_queryset(self, request):
        qs = super(SurveyTypeAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(SurveyType, SurveyTypeAdmin)
