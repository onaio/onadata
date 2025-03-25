from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm
from multidb.pinning import use_master
from onadata.apps.logger.models import Project


class Command(BaseCommand):
    help = "Assign `add_project_entitylist` permission to existing Owners and Managers"

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting permission assignment...")

        content_type = ContentType.objects.get_for_model(Project)
        perm_codename = "add_project_entitylist"

        with use_master:
            _, created = Permission.objects.get_or_create(
                codename=perm_codename,
                content_type=content_type,
                defaults={"name": "Can add entitylist to project"},
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Permission {perm_codename} created.")
                )

            project_qs = Project.objects.filter(deleted_at__isnull=True)
            eta = project_qs.count()

            for project in project_qs.iterator(chunk_size=200):
                project_user_obj_perm_qs = (
                    project.projectuserobjectpermission_set.filter(
                        permission__codename="add_project"
                    )
                )
                project_group_obj_perm_qs = (
                    project.projectgroupobjectpermission_set.filter(
                        permission__codename="add_project"
                    )
                )

                for user_obj_perm in project_user_obj_perm_qs.iterator(chunk_size=100):
                    user = get_user_model().objects.get(id=user_obj_perm.user_id)
                    assign_perm(perm_codename, user, project)

                for group_obj_perm in project_group_obj_perm_qs.iterator(
                    chunk_size=100
                ):
                    group = Group.objects.get(id=group_obj_perm.group_id)
                    assign_perm(perm_codename, group, project)

                eta -= 1
                self.stdout.write(f"Remaining: {eta}")

        self.stdout.write(self.style.SUCCESS("Permission assignment complete."))
