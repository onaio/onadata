from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from onadata.apps.logger.models.project import Project
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
            self.set_project_to_user_forms(user)

        print "Task completed ..."

    def set_project_to_user_forms(self, user):
        default_project_name = user.username + '\'s Project'
        try:
            project = Project.objects.get(name=default_project_name)
        except Project.DoesNotExist:
            metadata = {'description': 'Default Project'}
            project = Project.objects.create(name=default_project_name,
                                             organization=user,
                                             created_by=user,
                                             metadata=metadata)
            print "Created project " + project.name
        finally:
            xforms = user.xforms.filter(project=XFORM_DEFAULT_PROJECT_ID)

            for xform in queryset_iterator(xforms):
                xform.project = project
                xform.save()
