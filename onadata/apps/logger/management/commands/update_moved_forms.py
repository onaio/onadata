# -*- coding: utf-8 -*-
"""
Ensures all the forms are owned by the project owner
"""
from django.core.management import BaseCommand
from django.utils.translation import gettext_lazy

from onadata.apps.logger.models.project import Project
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    """
    Ensures all the forms are owned by the project owner
    """

    help = gettext_lazy("Ensures all the forms are owned by the project owner")

    def handle(self, *args, **kwargs):
        self.stdout.write("Updating forms owner", ending="\n")

        for project in queryset_iterator(Project.objects.all()):
            for xform in project.xform_set.all():
                try:
                    if xform.user != project.organization:
                        self.stdout.write(
                            f"Processing: {xform.id_string} - {xform.user.username}"
                        )
                        xform.user = project.organization
                        xform.save()
                # pylint: disable=broad-except
                except Exception:
                    self.stdout.write(
                        f"Error processing: {xform.id_string} - {xform.user.username}"
                    )
