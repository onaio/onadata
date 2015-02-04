from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from onadata.apps.api.models.team import Team
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.libs.utils.model_tools import queryset_iterator

from guardian.shortcuts import assign_perm, get_perms_for_model


class Command(BaseCommand):
    args = '<organization>'
    help = _(u"Assign permission to the member team")

    def handle(self, *args, **options):
        self.stdout.write("Assign permission to the member team", ending='\n')

        count = 0
        fail = 0
        total = 0
        if args:
            try:
                org_name = args[0]
                org = OrganizationProfile.objects.get(user__username=org_name)

                team = Team.objects.get(organization=org.user,
                                        name=u'%s#%s' % (
                                            org.user.username,
                                            'members'))
                self.assign_perm(team, org)
                count += 1
                total += 1

            except ObjectDoesNotExist as e:
                fail += 1
                self.stdout.write(str(e), ending='\n')
        else:
            # Get all the teams
            for team in queryset_iterator(
                    Team.objects.filter(name__contains='members')):
                self.assign_perm(team, team.organization)
                count += 1
                total += 1

        self.stdout.write("Assigned  {} of {} records. failed: {}".
                          format(count, total, fail), ending='\n')

    def assign_perm(self, team, org):
        for perm in get_perms_for_model(Team):
            org = org.user \
                if isinstance(org, OrganizationProfile) else org

            assign_perm(perm.codename, org, team)
            if team.created_by:
                assign_perm(perm.codename, team.created_by, team)
            if hasattr(org.profile, 'creator') and \
                    org.profile.creator != team.created_by:
                assign_perm(perm.codename,  org.profile.creator, team)
            if org.profile.created_by != team.created_by:
                assign_perm(perm.codename, org.profile.created_by, team)
