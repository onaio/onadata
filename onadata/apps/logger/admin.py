from django.contrib import admin

from onadata.apps.logger.models import XForm, Project


class FormAdmin(admin.ModelAdmin):

    exclude = ('user',)
    list_display = ('id_string', 'downloadable', 'shared')

    # A user should only see forms that belong to him.
    def get_queryset(self, request):
        qs = super(FormAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(XForm, FormAdmin)


class ProjectAdmin(admin.ModelAdmin):

    # A user should only see projects that belong to him.
    def get_queryset(self, request):
        qs = super(ProjectAdmin, self).queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

admin.site.register(Project, ProjectAdmin)
