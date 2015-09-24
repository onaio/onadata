from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from django.utils.translation import gettext as _
from django.conf import settings

from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.project import ProjectUserObjectPermission
from onadata.libs.utils.model_tools import queryset_iterator


class Command(BaseCommand):
    help = _(u"Migrate permissions")

    def handle(self, *args, **options):
        self.stdout.write("Migrate permissions started", ending='\n')
        ct = ContentType.objects.get(name=Project.__name__.lower(),
                                     app_label=Project._meta.app_label)
        # Get all the users
        users = User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)\
            .order_by('username')
        for user in queryset_iterator(users):
            for uop in user.userobjectpermission_set.filter(content_type=ct)\
                    .select_related('permission', 'content_type')\
                    .prefetch_related('permission', 'content_type'):
                try:
                    ProjectUserObjectPermission(
                        content_object=uop.content_object,
                        user=user,
                        permission=uop.permission
                    ).save()
                except IntegrityError:
                    continue
