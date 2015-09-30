from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _

from onadata.apps.api.models import Team
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.project import ProjectGroupObjectPermission
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Migrate group permissions")

    def handle(self, *args, **options):
        self.stdout.write("Migrate group permissions started", ending='\n')
        ct = ContentType.objects.get(name=Project.__name__.lower(),
                                     app_label=Project._meta.app_label)
        teams = Team.objects.filter().annotate(
            c=Count('groupobjectpermission')
        ).filter(c__gt=0)
        for team in queryset_iterator(teams):
            self.stdout.write(
                "Processing: {} - {}".format(team.pk, team.name)
            )
            for gop in team.groupobjectpermission_set.filter(content_type=ct)\
                    .select_related('permission', 'content_type')\
                    .prefetch_related('permission', 'content_type'):
                try:
                    ProjectGroupObjectPermission(
                        content_object=gop.content_object,
                        group=team,
                        permission=gop.permission
                    ).save()
                except IntegrityError:
                    continue
                except ValueError:
                    pass

        self.stdout.write("Group permissions migration done.")
