import json
from django.core.management.base import (
    BaseCommand, CommandError, CommandParser)
from django.utils.translation import gettext as _

from onadata.apps.logger.models import Project
from onadata.apps.api.models import OrganizationProfile
from onadata.libs.permissions import is_organization, get_role
from onadata.libs.serializers.organization_serializer import \
    OrganizationSerializer


def get_project_users(project):
    ret = {}

    for perm in project.projectuserobjectpermission_set.all():
        if perm.user.username not in ret:
            user = perm.user

            ret[user.username] = {
                'permissions': [],
                'is_org': is_organization(user.profile),
                'first_name': user.first_name,
                'last_name': user.last_name,
            }

        ret[perm.user.username]['permissions'].append(perm.permission.codename)

    for user in ret.keys():
        ret[user]['permissions'].sort()
        ret[user]['role'] = get_role(ret[user]['permissions'], project)
        del ret[user]['permissions']

    return ret


def get_organization_members(organization):
    ret = {}
    data = OrganizationSerializer().get_users(organization)

    for user_data in data:
        username = user_data.pop('user')
        user_data.pop('gravatar')
        ret[username] = user_data

    return ret


class Command(BaseCommand):
    help = _(
        "Retrieve collaborators list from all/a specific"
        " project(s) or organization(s)")

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--project-ids',
            '-p',
            default=None,
            dest='project_ids',
            help='Comma separated list of project ID(s) to'
            ' retrieve collaborators/members from.'
        )
        parser.add_argument(
            '--organization-ids',
            '-oid',
            default=None,
            dest='organization_ids',
            help='Comma separated list of organization ID(s) to retrieve'
            ' collaborators/members from.'
        )
        parser.add_argument(
            '--output-file',
            '-o',
            dest='output_file',
            default=None,
            help='JSON file to output the collaborators/members list too'
        )

    def handle(self, *args, **options):
        result = {}
        project_ids = options.get('project_ids')
        organization_ids = options.get('organization_ids')
        output_file = options.get('output_file')

        if project_ids or organization_ids:
            if project_ids:
                project_ids = project_ids.split(',')

                for project_id in project_ids:
                    try:
                        project = Project.objects.get(id=int(project_id))
                    except Project.DoesNotExist:
                        raise CommandError(
                            f'Project with ID {project_id} does not exist.')
                    except ValueError:
                        raise CommandError(
                            f'Invalid project ID input "{project_id}"')
                    else:
                        result[project.name] = get_project_users(project)

            if organization_ids:
                organization_ids = organization_ids.split(',')

                for org_id in organization_ids:
                    try:
                        org = OrganizationProfile.objects.get(
                            id=int(org_id))
                    except OrganizationProfile.DoesNotExist:
                        raise CommandError(
                            f'Organization with ID {org_id} does not exist.')
                    except ValueError:
                        raise CommandError(
                            f'Invalid organization ID input "{org_id}"')
                    else:
                        result[org.name] = get_organization_members(org)
        else:
            # Retrieve all Project & Organization members & organizations
            for project in Project.objects.filter(deleted_at__isnull=True):
                result[project.name] = get_project_users(project)

            for org in OrganizationProfile.objects.filter(
                    user__is_active=True):
                result[org.name] = get_organization_members(org)

        if output_file:
            with open(output_file, 'w+') as outfile:
                json.dump(result, outfile)
            self.stdout.write(
                f'Outputted members/collaborators list to "{output_file}"'
            )
        else:
            out = json.dumps(result)
            self.stdout.write(out)
