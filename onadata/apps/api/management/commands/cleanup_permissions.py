from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from guardian.models import UserObjectPermission
from guardian.models import GroupObjectPermission

from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Cleanup permissions")

    def handle(self, *args, **options):
        deleted = 0
        self.stdout.write("Starting UserObject")
        for perm in queryset_iterator(
                UserObjectPermission.objects.select_related()):
            try:
                perm.content_object
            except AttributeError:
                perm.delete()
                deleted += 1
                self.stdout.write(
                    "deleted {} stale permission".format(deleted)
                )
        self.stdout.write("Starting GroupObject")
        for perm in queryset_iterator(
                GroupObjectPermission.objects.select_related()):
            try:
                perm.content_object
            except AttributeError:
                perm.delete()
                deleted += 1
                self.stdout.write(
                    "deleted {} stale permission".format(deleted)
                )
        self.stdout.write(
            "Total removed orphan object permissions instances: %d" % deleted
        )
