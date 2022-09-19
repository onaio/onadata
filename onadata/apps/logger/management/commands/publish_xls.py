# -*- coding: utf-8 -*-
"""
publish_xls - Publish an XLSForm command.
"""
import os

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from pyxform.builder import create_survey_from_xls

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.logger_tools import publish_xls_form
from onadata.libs.utils.user_auth import get_user_default_project


class Command(BaseCommand):
    """Publish an XLSForm file."""

    args = "xls_file username project"
    help = gettext_lazy(
        "Publish an XLSForm file with the option of replacing an existing one"
    )

    def add_arguments(self, parser):
        parser.add_argument("xls_filepath")
        parser.add_argument("username")
        parser.add_argument(
            "-p", "--project-name", action="store_true", dest="project_name"
        )
        parser.add_argument(
            "-r",
            "--replace",
            action="store_true",
            dest="replace",
            help=gettext_lazy("Replace existing form if any"),
        )

    def handle(self, *args, **options):  # noqa C901
        # pylint: disable=invalid-name
        User = get_user_model()  # noqa N806
        try:
            xls_filepath = options["xls_filepath"]
        except KeyError as e:
            raise CommandError(_("You must provide the path to the xls file.")) from e
        # make sure path exists
        if not os.path.exists(xls_filepath):
            raise CommandError(_(f"The xls file '{xls_filepath}' does not exist."))

        try:
            username = options["username"]
        except KeyError as e:
            raise CommandError(
                _("You must provide the username to publish the form to.")
            ) from e
        # make sure user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as e:
            raise CommandError(_(f"The user '{username}' does not exist.")) from e

        # wasteful but we need to get the id_string beforehand
        survey = create_survey_from_xls(xls_filepath)

        # check if a form with this id_string exists for this user
        form_already_exists = (
            XForm.objects.filter(user=user, id_string=survey.id_string).count() > 0
        )

        # id_string of form to replace, if any
        id_string = None
        if form_already_exists:
            if "replace" in options and options["replace"]:
                id_string = survey.id_string
                self.stdout.write(_("Form already exist, replacing ..\n"))
            else:
                raise CommandError(
                    _(
                        f"The form with id_string '{survey.id_string}' already exists,"
                        " use the -r option to replace it."
                    )
                )
        else:
            self.stdout.write(_("Form does NOT exist, publishing ..\n"))

        try:
            project_name = options["project_name"]
            project = Project.objects.get(name=project_name)
        except (KeyError, Project.DoesNotExist):
            project = get_user_default_project(user)

        # publish
        with open(xls_filepath, "rb") as file_object:
            with InMemoryUploadedFile(
                file=file_object,
                field_name="xls_file",
                name=file_object.name,
                content_type="application/vnd.ms-excel",
                size=os.path.getsize(xls_filepath),
                charset=None,
            ) as xls_file:
                publish_xls_form(xls_file, user, project, id_string)
                self.stdout.write(_("Done..\n"))
