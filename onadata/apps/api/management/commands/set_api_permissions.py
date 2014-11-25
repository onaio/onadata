from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs.permissions import OwnerRole
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.user_auth import set_api_permissions_for_user


class Command(BaseCommand):
    help = _(u"Set object permissions for all objects.")

    def handle(self, *args, **options):
        # XForms
        for xform in queryset_iterator(XForm.objects.all()):
            OwnerRole.add(xform.user, xform)

        # UserProfile
        for profile in queryset_iterator(UserProfile.objects.all()):
            set_api_permissions_for_user(profile.user)
            OwnerRole.add(profile.user, profile)

            if profile.created_by is not None:
                OwnerRole.add(profile.created_by, profile)

        # OrganizationProfile
        for profile in queryset_iterator(OrganizationProfile.objects.all()):
            OwnerRole.add(profile.user, profile)

            if profile.created_by is not None:
                OwnerRole.add(profile.created_by, profile)

            if profile.creator is not None:
                OwnerRole.add(profile.creator, profile)

        # Project
        for project in queryset_iterator(Project.objects.all()):
            OwnerRole.add(project.organization, project)
            OwnerRole.add(project.created_by, project)
