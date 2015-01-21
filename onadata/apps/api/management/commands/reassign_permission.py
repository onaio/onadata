from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.conf import settings


from onadata.libs.permissions import ReadOnlyRole, DataEntryRole,\
    EditorRole, ManagerRole, OwnerRole


class Command(BaseCommand):
    args = '<app model [created_perm] >'
    help = _(u"Reassign permission to the model when permissions are changed")

    def handle(self, *args, **options):
        self.stdout.write("Re-assigining started", ending='\n')

        if not args:
            raise CommandError('Param not set. <app model [created_perm]>')

        if len(args) < 3:
            raise CommandError('Param not set. <app model [created_perm]>')

        app = args[0]
        model = args[1]
        new_perm = args[2]

        self.reassign_perms(User.objects.get(username='ukanga'), app, model,
                            new_perm)
        exit()

        from onadata.libs.utils.model_tools import queryset_iterator
        # Get all the users
        for user in queryset_iterator(
                User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)):
            self.reassign_perms(user, app, model, new_perm)

        self.stdout.write("Re-assigining finished", ending='\n')

    def reassign_perms(self, user, app, model, new_perm):
        cont_type = ContentType.objects.get(app_label=app,
                                            model=model)
        objects = user.userobjectpermission_set.filter(content_type=cont_type)\
            .distinct('object_pk')

        for perm_obj in objects:
            obj = perm_obj.content_object
            ROLES = [ReadOnlyRole,
                     DataEntryRole,
                     EditorRole,
                     ManagerRole,
                     OwnerRole]

            for role_class in reversed(ROLES):

                if self.check_role(role_class, user, obj, new_perm):
                    if obj.pk == 13:
                        self.stdout.write("Found " + role_class.name + " "
                                          + obj.name + " " + user.username)
                    break

    def check_role(self, role_class, user, obj, new_perm):
        # remove the new permission
        perm_list = role_class.class_to_permissions[type(obj)]
        if new_perm in perm_list:
            # Make a copy so that we can modify it
            copy_list = perm_list[:]
            copy_list.remove(new_perm)

            return user.has_perms(copy_list, obj)
