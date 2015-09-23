from django.forms import widgets
from rest_framework import serializers
from django.core.cache import cache
from django.db.models import Prefetch

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import Project
from onadata.libs.permissions import get_object_users_with_permissions,\
    OwnerRole, ReadOnlyRole, is_organization
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.serializers.xform_serializer import XFormSerializer
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.cache_tools import (
    PROJ_FORMS_CACHE, PROJ_NUM_DATASET_CACHE, PROJ_PERM_CACHE,
    PROJ_SUB_DATE_CACHE, safe_delete, PROJ_TEAM_USERS_CACHE)
from onadata.apps.api.models import Team
from onadata.libs.permissions import get_team_project_default_permissions
from onadata.apps.api.tools import (
    get_organization_members_team, get_organization_owners_team)


def set_owners_permission(user, project):
    """Give the user owner permission"""
    OwnerRole.add(user, project)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    projectid = serializers.Field(source='id')
    url = serializers.HyperlinkedIdentityField(
        view_name='project-detail', lookup_field='pk')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='organization',
        lookup_field='username')
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='created_by',
        lookup_field='username',
        read_only=True)
    metadata = JsonField(source='metadata', required=False)
    starred = serializers.SerializerMethodField('is_starred_project')
    users = serializers.SerializerMethodField('get_project_permissions')
    forms = serializers.SerializerMethodField('get_project_forms')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField('get_num_datasets')
    last_submission_date = serializers.SerializerMethodField(
        'get_last_submission_date')
    teams = serializers.SerializerMethodField('get_team_users')

    class Meta:
        model = Project
        exclude = ('organization', 'user_stars')

    def restore_object(self, attrs, instance=None):
        if instance:
            metadata = JsonField.to_json(attrs.get('metadata'))
            owner = attrs.get('organization')

            if self.partial and metadata:
                if not isinstance(instance.metadata, dict):
                    instance.metadata = {}

                instance.metadata.update(metadata)
                attrs['metadata'] = instance.metadata

            if self.partial and owner:
                # give the new owner permissions
                set_owners_permission(owner, instance)

                if is_organization(owner.profile):
                    owners_team = get_organization_owners_team(owner.profile)
                    members_team = get_organization_members_team(owner.profile)
                    OwnerRole.add(owners_team, instance)
                    ReadOnlyRole.add(members_team, instance)

                # clear cache
                safe_delete('{}{}'.format(PROJ_PERM_CACHE, self.object.pk))

            return super(ProjectSerializer, self).restore_object(
                attrs, instance)

        if 'request' in self.context:
            created_by = self.context['request'].user

            return Project(
                name=attrs.get('name'),
                organization=attrs.get('organization'),
                created_by=created_by,
                metadata=attrs.get('metadata'),)

        return attrs

    def save_object(self, obj, **kwargs):
        super(ProjectSerializer, self).save_object(obj, **kwargs)

        obj.xform_set.exclude(shared=obj.shared)\
            .update(shared=obj.shared, shared_data=obj.shared)

    def get_project_permissions(self, obj):
        if obj:
            users = cache.get('{}{}'.format(PROJ_PERM_CACHE, obj.pk))
            if users:
                return users

            user = get_object_users_with_permissions(obj)
            cache.set('{}{}'.format(PROJ_PERM_CACHE, obj.pk), user)

            return user

        return []

    @check_obj
    def get_project_forms(self, obj):
        if obj:
            forms = cache.get('{}{}'.format(PROJ_FORMS_CACHE, obj.pk))
            if forms:
                return forms
            xforms = obj.xform_set.prefetch_related(
                Prefetch('metadata_set')
            )

            request = self.context.get('request')
            serializer = XFormSerializer(xforms, context={'request': request},
                                         many=True)

            forms = [{'name': form['title'],
                      'formid':form['formid'],
                      'num_of_submissions':form['num_of_submissions'],
                      'downloadable':form['downloadable'],
                      'last_submission_time':form['last_submission_time'],
                      'date_created':form['date_created'],
                      'url': form['url'],
                      'enketo_url': form['enketo_url'],
                      'enketo_preview_url': form['enketo_preview_url'],
                      'data_views': form['data_views']
                      }
                     for form in serializer.data]
            cache.set('{}{}'.format(PROJ_FORMS_CACHE, obj.pk), forms)
            return forms

        return []

    @check_obj
    def get_num_datasets(self, obj):
        """Return the number of datasets attached to the object.

        :param obj: The project to find datasets for.
        """
        if obj:
            count = cache.get('{}{}'.format(PROJ_NUM_DATASET_CACHE, obj.pk))
            if count:
                return count

            count = obj.xform_set.count()
            cache.set('{}{}'.format(PROJ_NUM_DATASET_CACHE, obj.pk), count)
            return count

        return None

    @check_obj
    def get_last_submission_date(self, obj):
        """Return the most recent submission date to any of the projects
        datasets.

        :param obj: The project to find the last submission date for.
        """
        if obj:
            last_submission = cache.get('{}{}'.format(
                PROJ_SUB_DATE_CACHE, obj.pk))
            if last_submission:
                return last_submission

            xform_ids = obj.xform_set.values_list('pk', flat=True)
            last_submission = Instance.objects.\
                order_by('-date_created').\
                filter(xform_id__in=xform_ids).values_list('date_created',
                                                           flat=True)
            cache.set('{}{}'.format(PROJ_SUB_DATE_CACHE, obj.pk),
                      last_submission and last_submission[0])
            return last_submission and last_submission[0]

        return None

    def is_starred_project(self, obj):
        request = self.context['request']
        user = request.user
        user_stars = obj.user_stars.all()
        if user in user_stars:
            return True

        return False

    def get_team_users(self, obj):
        if obj:
            teams_users = cache.get('{}{}'.format(
                PROJ_TEAM_USERS_CACHE, obj.pk))
            if teams_users:
                return teams_users

            teams_users = []
            teams = Team.objects.filter(organization=obj.organization)

            for team in teams:
                users = []
                for user in team.user_set.all():
                    users.append(user.username)

                teams_users.append({
                    "name": team.name,
                    "role": get_team_project_default_permissions(team, obj),
                    "users": users
                })

            cache.set('{}{}'.format(PROJ_TEAM_USERS_CACHE, obj.pk),
                      teams_users)
            return teams_users

        return []
