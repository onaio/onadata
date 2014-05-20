from django.contrib.auth.models import User
from rest_framework import serializers

from onadata.libs.serializers.fields.hyperlinked_multi_identity_field import\
    HyperlinkedMultiIdentityField
from onadata.libs.serializers.fields.hyperlinked_multi_related_field import\
    HyperlinkedMultiRelatedField
from onadata.apps.api.models import Project, OrganizationProfile, Team


class TeamSerializer(serializers.Serializer):
    url = HyperlinkedMultiIdentityField(
        view_name='team-detail',
        lookup_fields=(('pk', 'pk'), ('owner', 'organization')))
    name = serializers.CharField(max_length=100, source='team_name')
    organization = serializers.SlugRelatedField(
        slug_field='username',
        source='organization',
        queryset=User.objects.filter(
            pk__in=OrganizationProfile.objects.values('user')))
    projects = HyperlinkedMultiRelatedField(
        view_name='project-detail', source='projects', many=True,
        queryset=Project.objects.all(), read_only=True,
        lookup_fields=(('pk', 'pk'), ('owner', 'organization')))

    def restore_object(self, attrs, instance=None):
        org = attrs.get('organization', None)
        projects = attrs.get('projects', [])
        if instance:
            instance.organization = org if org else instance.organization
            instance.name = attrs.get('team_name', instance.name)
            instance.projects.clear()
            for project in projects:
                instance.projects.add(project)
            return instance
        team_name = attrs.get('team_name', None)
        if not team_name:
            self.errors['name'] = u'A team name is required'
            return attrs
        return Team(organization=org, name=team_name)
