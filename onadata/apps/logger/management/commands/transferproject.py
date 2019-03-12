"""Functionality to transfer a project from one owner to another."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from onadata.apps.logger.models import Project, XForm, DataView, MergedXForm
from onadata.apps.logger.models.project import set_object_permissions \
    as set_project_permissions
from onadata.libs.utils.project_utils import set_project_perms_to_xform


class Command(BaseCommand):
    """
    Command to transfer a project from one user to the other.

    Usage:
    The mandatory arguments are --current-owner, --new-owner and either of
    --project-id or --all-projects.
    Depending on what is supplied for --project-id or --all-projects,
    the command will either transfer a single project or all the projects.
    """
    help = 'A command to reassign a project(s) from one user to the other.'

    errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--current-owner',
            dest='current_owner',
            type=str,
            help='Username of the current owner of the project(s)',
        )
        parser.add_argument(
            '--new-owner',
            dest='new_owner',
            type=str,
            help='Username of the new owner of the project(s)',
        )
        parser.add_argument(
            '--project-id',
            dest='project_id',
            type=int,
            help='Id of the project to be transferred.',
        )
        parser.add_argument(
            '--all-projects',
            dest='all_projects',
            action='store_true',
            help='Supply this command if all the projects are to be'
            ' transferred. If not, do not include the argument',
        )

    def get_user(self, username):  # pylint: disable=C0111
        user_model = get_user_model()
        user = None
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.errors.append("User {0} does not exist".format(username))
        return user

    def update_xform_with_new_user(self, project, user):
        """
        Update XForm user update the DataViews and also set the permissions
        for the xForm and the project.
        """
        xforms = XForm.objects.filter(
            project=project, deleted_at__isnull=True, downloadable=True)
        for form in xforms:
            form.user = user
            form.created_by = user
            form.save()
            self.update_data_views(form)
            set_project_perms_to_xform(form, project)

    @staticmethod
    def update_data_views(form):
        """Update DataView project for the XForm given. """
        dataviews = DataView.objects.filter(
            xform=form, project=form.project, deleted_at__isnull=True)
        for data_view in dataviews:
            data_view.project = form.project
            data_view.save()

    @staticmethod
    def update_merged_xform(project, user):
        """Update ownership of MergedXforms."""
        merged_xforms = MergedXForm.objects.filter(
            project=project, deleted_at__isnull=True)
        for form in merged_xforms:
            form.user = user
            form.created_by = user
            form.save()
            set_project_perms_to_xform(form, project)

    @transaction.atomic()
    def handle(self, *args, **options):
        """Transfer projects from one user to another."""
        from_user = self.get_user(options['current_owner'])
        to_user = self.get_user(options['new_owner'])
        project_id = options.get('project_id')
        transfer_all_projects = options.get('all_projects')

        if self.errors:
            self.stdout.write(''.join(self.errors))
            return

        # No need to validate project ownership as they filtered
        # against current_owner
        projects = []
        if transfer_all_projects:
            projects = Project.objects.filter(
                organization=from_user, deleted_at__isnull=True)
        else:
            projects = Project.objects.filter(
                id=project_id, organization=from_user)

        for project in projects:
            project.organization = to_user
            project.created_by = to_user
            project.save()

            self.update_xform_with_new_user(project, to_user)
            self.update_merged_xform(project, to_user)
            set_project_permissions(Project, project, created=True)

        self.stdout.write('Projects transferred successfully')
