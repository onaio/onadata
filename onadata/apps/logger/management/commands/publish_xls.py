import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from pyxform.builder import create_survey_from_xls

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.logger_tools import publish_xls_form
from onadata.libs.utils.user_auth import get_user_default_project
from onadata.libs.utils.viewer_tools import django_file


class Command(BaseCommand):
    args = 'xls_file username project'
    help = ugettext_lazy("Publish an XLS file with the option of replacing an"
                         "existing one")

    def add_arguments(self, parser):
        parser.add_argument('xls_filepath')
        parser.add_argument('username')
        parser.add_argument(
            '-p', '--project-name', action='store_true', dest='project_name')
        parser.add_argument(
            '-r',
            '--replace',
            action='store_true',
            dest='replace',
            help=ugettext_lazy("Replace existing form if any"))

    def handle(self, *args, **options):
        try:
            xls_filepath = options['xls_filepath']
        except KeyError:
            raise CommandError(_("You must provide the path to the xls file."))
        # make sure path exists
        if not os.path.exists(xls_filepath):
            raise CommandError(
                _("The xls file '%s' does not exist.") % xls_filepath)

        try:
            username = options['username']
        except KeyError:
            raise CommandError(
                _("You must provide the username to publish the form to."))
        # make sure user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(_("The user '%s' does not exist.") % username)

        # wasteful but we need to get the id_string beforehand
        survey = create_survey_from_xls(xls_filepath)

        # check if a form with this id_string exists for this user
        form_already_exists = XForm.objects.filter(
            user=user, id_string=survey.id_string).count() > 0

        # id_string of form to replace, if any
        id_string = None
        if form_already_exists:
            if 'replace' in options and options['replace']:
                id_string = survey.id_string
                self.stdout.write(_("Form already exist, replacing ..\n"))
            else:
                raise CommandError(
                    _("The form with id_string '%s' already exists, use the -r"
                      " option to replace it.") % survey.id_string)
        else:
            self.stdout.write(_("Form does NOT exist, publishing ..\n"))

        try:
            project_name = options['project_name']
            project = Project.objects.get(name=project_name)
        except (KeyError, Project.DoesNotExist):
            project = get_user_default_project(user)

        # publish
        xls_file = django_file(xls_filepath, 'xls_file',
                               'application/vnd.ms-excel')
        publish_xls_form(xls_file, user, project, id_string)
        self.stdout.write(_("Done..\n"))
