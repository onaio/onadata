from django.utils.translation import gettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Check for forms not in a project"
             u" and move them to the default project")

    def handle(self, *args, **options):
        print "Task started ..."

        # Get all the users
        for user in queryset_iterator(User.objects.all()):
            # For each user get the forms which are projectless
            for form in queryset_iterator(XForm.objects
                                          .select_related('projectxform')
                                          .filter(projectxform=None,
                                                  user=user)):

                # Create the default project
                self.create_and_assign_project(user, form)

        print "Task completed ..."

    def create_and_assign_project(self, user, form):
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
        ProjectXForm.objects.create(xform=form,
                                    project=project,
                                    created_by=user)
        print "Added " + form.id_string + " to project " + project.name
