from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.project_xform import ProjectXForm
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


XFORM_DEFAULT_PROJECT_ID = 1


class Command(BaseCommand):
    help = _(u"Check for forms not in a project"
             u" and move them to the default project")

    def handle(self, *args, **options):
        print "Task started ..."

        # Get all the users
        for user in queryset_iterator(
                User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)):
            # For each user get the forms which are projectless
            xforms = XForm.objects.select_related('px_xforms').filter(
                px_xforms=None, user=user)

            for xform in queryset_iterator(xforms):
                # Create the default project
                self.create_and_assign_project(user, xform)

            self.set_project_to_user_forms(user)

        print "Task completed ..."

    def set_project_to_user_forms(self, user):
        default_project_name = user.username + '\'s Project'
        try:
            project = Project.objects.get(name=default_project_name)
        except Project.DoesNotExist:
            pass
        else:
            xforms = XForm.objects.select_related('px_xforms').filter(
                project=XFORM_DEFAULT_PROJECT_ID)

            for xform in queryset_iterator(xforms):
                if xform.px_xforms.count():
                    xform.project = xform.px_xforms.all()[0].project
                else:
                    xform.project = project

                xform.save()

    def create_and_assign_project(self, user, xform):
        name = user.username + '\'s Project'
        # Check if exists first
        projects = Project.objects.filter(organization=user, name=name)

        if not len(projects):
            metadata = {'description': 'Default Project'}
            project = Project.objects.create(name=name,
                                             organization=user,
                                             created_by=user,
                                             metadata=metadata)
            print "Created project " + project.name
        else:
            project = projects[0]

        # Link the project to the form
        ProjectXForm.objects.create(xform=xform,
                                    project=project,
                                    created_by=user)
        xform.project = project
        xform.save()

        print "Added " + xform.id_string + " to project " + project.name
