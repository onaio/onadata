from django.core.management import BaseCommand
from django.utils.translation import ugettext_lazy

from onadata.apps.logger.models.project import Project
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = ugettext_lazy("Ensures all the forms are owned by the project"
                         " owner")

    def handle(self, *args, **kwargs):
        self.stdout.write("Updating forms owner", ending='\n')

        for project in queryset_iterator(Project.objects.all()):
            for xform in project.xform_set.all():
                try:
                    if xform.user != project.organization:
                        self.stdout.write(
                            "Processing: {} - {}".format(xform.id_string,
                                                         xform.user.username)
                        )
                        xform.user = project.organization
                        xform.save()
                except Exception:
                    self.stdout.write(
                        "Error processing: {} - {}".format(xform.id_string,
                                                           xform.user.username)
                    )
                    pass
