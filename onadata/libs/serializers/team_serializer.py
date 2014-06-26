from django.contrib.auth.models import User
from rest_framework import serializers

from onadata.libs.serializers.fields.hyperlinked_multi_identity_field import\
    HyperlinkedMultiIdentityField
from onadata.libs.serializers.user_serializer import UserSerializer
from onadata.apps.api.models import Project, OrganizationProfile, Team


class TeamSerializer(serializers.Serializer):
    url = HyperlinkedMultiIdentityField(
        view_name='team-detail')
    name = serializers.CharField(max_length=100, source='team_name')
    organization = serializers.SlugRelatedField(
        slug_field='username',
        source='organization',
        queryset=User.objects.filter(
            pk__in=OrganizationProfile.objects.values('user')))
    projects = serializers.HyperlinkedRelatedField(view_name='project-detail',
                                                   source='projects',
                                                   many=True,
                                                   read_only=True)
    users = serializers.SerializerMethodField('get_team_users')

    def get_team_users(self, obj):
        users = []

        for user in obj.user_set.all():
            users.append(UserSerializer(instance=user).data)

        return users

    def restore_object(self, attrs, instance=None):
        org = attrs.get('organization', None)
        projects = attrs.get('projects', [])
        team_name = attrs.get('team_name', None)
        request = self.context.get('request')
        created_by = request.user

        if instance:
            instance.organization = org if org else instance.organization
            instance.name = attrs.get('team_name', instance.name)
            instance.projects.clear()

            for project in projects:
                instance.projects.add(project)

            return instance

        if not team_name:
            self.errors['name'] = u'A team name is required'
            return attrs

        return Team(organization=org, name=team_name, created_by=created_by)
