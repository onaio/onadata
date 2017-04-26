from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.loading import get_model
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _
from guardian.models import GroupObjectPermissionBase

from onadata.apps.api.models import Team
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Migrate group permissions")

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            '-m',
            action='store_true',
            dest='app_model',
            default=False,
            help='The model the permission belong too.'
            ' (app.model format)')
        parser.add_argument(
            '--perm-table',
            '-p',
            action='store_true',
            dest='perms_tbl',
            default=False,
            help='The new model permission are stored in'
            ' (app.model format)')

    def handle(self, *args, **options):
        self.stdout.write("Migrate group permissions started", ending='\n')

        if len(args) < 2:
            self.stdout.write("This command takes two argument -m and -p "
                              "Example: "
                              "-m logger.Team "
                              "-p logger.TeamUserObjectPermission")
            exit()

        if options['app_model']:
            app_model = args[0]
        else:
            self.stdout.write("-m , should be set as the first argument")
            exit()

        if options['perms_tbl']:
            perms_tbl = args[1]
        else:
            self.stdout.write("-p , should be set as the second argument")
            exit()

        model = get_model(app_model)
        perms_model = get_model(perms_tbl)

        if not issubclass(perms_model, GroupObjectPermissionBase):
            self.stdout.write("-p , should be a model of a class that is "
                              "a subclass of GroupObjectPermissionBase")
            exit()

        ct = ContentType.objects.get(
            model=model.__name__.lower(), app_label=model._meta.app_label)
        teams = Team.objects.filter().annotate(
            c=Count('groupobjectpermission')).filter(c__gt=0)
        for team in queryset_iterator(teams):
            self.stdout.write("Processing: {} - {}".format(team.pk, team.name))
            for gop in team.groupobjectpermission_set.filter(content_type=ct)\
                    .select_related('permission', 'content_type')\
                    .prefetch_related('permission', 'content_type'):
                try:
                    perms_model(
                        content_object=gop.content_object,
                        group=team,
                        permission=gop.permission).save()
                except IntegrityError:
                    continue
                except ValueError:
                    pass

        self.stdout.write("Group permissions migration done.")
