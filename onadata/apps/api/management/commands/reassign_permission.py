from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.conf import settings
from guardian.shortcuts import (
    assign_perm,
    remove_perm,
    get_perms,
    get_users_with_perms)


from onadata.libs.permissions import ReadOnlyRole, DataEntryRole,\
    EditorRole, ManagerRole, OwnerRole, get_role_in_org


class Command(BaseCommand):
    help = _(u"Reassign permission to the model when permissions are changed")

    def handle(self, *args, **options):
        print "Task started ..."

        self.reassign_perms(User.objects.get(username='ukanga'))
        exit()

        from onadata.libs.utils.model_tools import queryset_iterator
        # Get all the users
        for user in queryset_iterator(
                User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)):
            self.reassign_perms(user)

        print "Task completed ..."


    def reassign_perms(self, user):
        cont_type = ContentType.objects.get(app_label='logger',
                                            model='project')

        permission = Permission.objects.filter(content_type=cont_type)

        objects = user.userobjectpermission_set.filter(content_type=cont_type)\
            .distinct('object_pk')

        for perm_obj in objects:
            object = perm_obj.content_object
            ROLES = [ReadOnlyRole,
                     DataEntryRole,
                     EditorRole,
                     ManagerRole,
                     OwnerRole]

            for role_class in reversed(ROLES):

                if self.check_role(role_class, user, object):
                    if object.pk ==13:
                        print "Found "+role_class.name+" "+object.name+" "+user.username
                    break



        #print "Done"

    def check_role(self, role_class, user, object):
        new_perm = 'report_project_xform'
        # remove the new permission
        perm_list = role_class.class_to_permissions[type(object)]
        if new_perm in perm_list:
            # Make a copy so that we can modify it
            copy_list = perm_list[:]
            copy_list.remove(new_perm)

            return user.has_perms(copy_list, object)
        else:
            return