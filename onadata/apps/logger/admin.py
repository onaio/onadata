from reversion.admin import VersionAdmin

from django.contrib import admin

from onadata.apps.logger.models import (
    XForm, Project, Attachment, DataView, Note, OsmData, SurveyType, Widget)


class FormAdmin(VersionAdmin, admin.ModelAdmin):
    exclude = ('user',)
    list_display = ('id_string', 'downloadable', 'shared')
    search_fields = ('id_string', 'title')

    # A user should only see forms that belong to him.
    def get_queryset(self, request):
        qs = super(FormAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(XForm, FormAdmin)


class ProjectAdmin(admin.ModelAdmin):
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


class AttachmentAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('media_file',)
    search_fields = ('media_file',)

    def get_queryset(self, request):
        qs = super(AttachmentAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Attachment, AttachmentAdmin)


class DataViewAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('name', 'xform', 'project')
    search_fields = ('name', 'xform__id_string', 'project__name')

    def get_queryset(self, request):
        qs = super(DataViewAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(DataView, DataViewAdmin)


class NoteAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('note',)

    def get_queryset(self, request):
        qs = super(NoteAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Note, NoteAdmin)


class OsmDataAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('filename', 'field_name')

    def get_queryset(self, request):
        qs = super(OsmDataAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(OsmData, OsmDataAdmin)


class SurveyTypeAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('slug',)

    def get_queryset(self, request):
        qs = super(SurveyTypeAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(SurveyType, SurveyTypeAdmin)


class WidgetAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ('object_id', 'title', 'key')

    def get_queryset(self, request):
        qs = super(WidgetAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Widget, WidgetAdmin)
