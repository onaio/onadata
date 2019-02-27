"""Functionality to transfer a project form one owner to another."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from onadata.apps.logger.models import Project, XForm, DataView, MergedXForm
from onadata.apps.logger.models.project import set_object_permissions \
    as set_project_permissions
from onadata.libs.utils.project_utils import set_project_perms_to_xform
from onadata.libs.utils.viewer_tools import get_form_url, enketo_url
from onadata.apps.main.models.meta_data import unique_type_for_form


class Command(BaseCommand):  # pylint: disable=C0111
    help = 'A command to reassign a project form one user to the other.'

    errors = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--currentowner',
            help='Username of the current owner of of the projects',
        )
        parser.add_argument(
            '--newowner',
            help='TUsername of new owner of the projects',
        )
        parser.add_argument(
            '--httphost',
            help='The http host for the server e.g ona.io',
        )
        parser.add_argument(
            '--httpprotocol',
            help='The protocol to use for enketo url: https or http',
        )

    def get_user(self, username):  # pylint: disable=C0111
        user_model = get_user_model()
        user = None
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.errors.append("User {0} does not exist \n".format(username))
        return user

    def update_xform_with_new_user(self, project, user):
        """
        Update XForm user update the DataViews and also set the permissions
        for the xform and the project.
        """
        xforms = XForm.objects.filter(
            project=project, deleted_at__isnull=True, downloadable=True)
        for form in xforms:
            form.user = user
            form.created_by = user
            form.save()
            self.update_data_views(form)
            set_project_perms_to_xform(form, project)
            self.update_enketo_urls(form)

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
        merged_xforms = MergedXForm.objects.filter(
            project=project, deleted_at__isnull=True)
        for form in merged_xforms:
            form.user = user
            form.created_by = user
            form.save()
            set_project_perms_to_xform(form, project)

    def update_enketo_urls(self, form):
        form_url = get_form_url(
            request=None, username=form.user.username,
            protocol=self.httpprotocol, preview=False, xform_pk=form.pk,
            http_host=self.httphost
        )
        url = enketo_url(
            form_url=form_url, id_string=form.id_string, instance_xml=form.xml,
            instance_id=form.id, return_url=None,
        )
        unique_type_for_form(
            content_object=form, data_type='enketo_url', data_value=url,
            data_file=None
        )

    @transaction.atomic()
    def handle(self, *args, **options):
        """Transfer projects from one user to another."""
        from_user = self.get_user(options['currentowner'])
        to_user = self.get_user(options['newowner'])
        self.httphost = options['httphost']
        self.httpprotocol = options['httpprotocol']

        if self.errors:
            self.stdout.write(self.style.ERROR(''.join(self.errors)))
            return

        projects = Project.objects.filter(
            organization=from_user, deleted_at__isnull=True)
        for project in projects:
            project.organization = to_user
            project.created_by = to_user
            project.save()

            self.update_xform_with_new_user(project, to_user)
            self.update_merged_xform(project, to_user)
            set_project_permissions(Project, project, created=True)

        old_user_projects_count = Project.objects.filter(
            organization=from_user).count()
        assert old_user_projects_count == 0

        self.stdout.write(
            self.style.SUCCESS('Projects transferred successfully')
        )
