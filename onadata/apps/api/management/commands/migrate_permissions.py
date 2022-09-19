# -*- coding: utf-8 -*-
"""
Migrate permissions
"""
import sys

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _

from guardian.models import UserObjectPermissionBase

from onadata.libs.utils.model_tools import queryset_iterator

User = get_user_model()


class Command(BaseCommand):
    """Migrate permissions"""

    help = _("Migrate permissions")

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            "-m",
            action="store_true",
            dest="app_model",
            default=False,
            help="The model the permission belong too." " (app.model format)",
        )
        parser.add_argument(
            "--perm-table",
            "-p",
            action="store_true",
            dest="perms_tbl",
            default=False,
            help="The new model permission are stored in" " (app.model format)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Migrate permissions started", ending="\n")

        if len(args) < 2:
            self.stdout.write(
                "This command takes two argument -m and -p "
                "Example: "
                "-m logger.Team "
                "-p logger.TeamUserObjectPermission"
            )
            sys.exit()

        if options["app_model"]:
            app_model = args[0]
        else:
            self.stdout.write("-m , should be set as the first argument")
            sys.exit()

        if options["perms_tbl"]:
            perms_tbl = args[1]
        else:
            self.stdout.write("-p , should be set as the second argument")
            sys.exit()

        model = apps.get_model(app_model)
        perms_model = apps.get_model(perms_tbl)

        if not issubclass(perms_model, UserObjectPermissionBase):
            self.stdout.write(
                "-p , should be a model of a class that is "
                "a subclass of UserObjectPermissionBase"
            )
            sys.exit()

        content_type = ContentType.objects.get(
            model=model.__name__.lower(), app_label=model._meta.app_label
        )

        # Get all the users
        users = User.objects.exclude(
            username__iexact=settings.ANONYMOUS_DEFAULT_USERNAME
        ).order_by("username")

        for user in queryset_iterator(users):
            self.stdout.write(f"Processing: {user.pk} - {user.username}")
            for uop in (
                user.userobjectpermission_set.filter(content_type=content_type)
                .select_related("permission", "content_type")
                .prefetch_related("permission", "content_type")
            ):
                try:
                    perms_model(
                        content_object=uop.content_object,
                        user=user,
                        permission=uop.permission,
                    ).save()
                except IntegrityError:
                    continue
                except ValueError:
                    pass
