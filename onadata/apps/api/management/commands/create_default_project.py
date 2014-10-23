from django.utils.translation import gettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from onadata.apps.api.models.project import Project
from onadata.apps.api.models.project_xform import ProjectXForm
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.permissions import OwnerRole


class Command(BaseCommand):
    help = _(u"Check for forms not in a project"
             u" and move them to the default project")

    def handle(self, *args, **options):
        print "Task started ..."

        # Get all the users
        for user in queryset_iterator(User.objects.all()):

            # For each user get the forms
            for form in queryset_iterator(XForm.objects.filter(user=user)):

                # Check if each form is in a project
                if not ProjectXForm.objects.filter(xform=form).exists():

                    # Create the default project
                    project = self.create_and_assign_project(user, form)

                    print "Project: "+project.name

        print "Task completed ..."

    def create_and_assign_project(self, user, form):
        name = '['+user.username + ']\'s Project'
        # Check if exists first
        projects = Project.objects.filter(organization=user, name=name)

        if not len(projects):
            project = Project.objects.create(name=name,
                                             organization=user,
                                             created_by=user)
        else:
            project = projects[0]

        # Link the project to the form
        ProjectXForm.objects.create(xform=form,
                                    project=project,
                                    created_by=user)
        # Add Role
        OwnerRole.add(project.organization, project)
        return project
