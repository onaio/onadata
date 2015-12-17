from rest_framework import serializers
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils.translation import ugettext as _

from onadata.apps.logger.models import Project
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import OwnerRole
from onadata.libs.permissions import ReadOnlyRole
from onadata.libs.permissions import is_organization
from onadata.libs.permissions import get_role
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.libs.utils.decorators import check_obj
from onadata.libs.utils.cache_tools import (
    BASE_PROJ_FORMS_CACHE,
    BASE_PROJ_USERS_CACHE,
    PROJ_FORMS_CACHE, PROJ_NUM_DATASET_CACHE, PROJ_PERM_CACHE,
    PROJ_SUB_DATE_CACHE, safe_delete, PROJ_TEAM_USERS_CACHE,
    PROJECT_LINKED_DATAVIEWS)
from onadata.apps.api.tools import (
    get_organization_members_team, get_organization_owners_team)
from onadata.libs.utils.profiler import profile


def set_owners_permission(user, project):
    """Give the user owner permission"""
    OwnerRole.add(user, project)


class BaseProjectXFormSerializer(serializers.HyperlinkedModelSerializer):
    formid = serializers.ReadOnlyField(source='id')
    name = serializers.ReadOnlyField(source='title')

    class Meta:
        model = XForm
        fields = ('name', 'formid')


class ProjectXFormSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='xform-detail',
                                               lookup_field='pk')
    formid = serializers.ReadOnlyField(source='id')
    name = serializers.ReadOnlyField(source='title')

    class Meta:
        model = XForm
        fields = (
            'name', 'formid', 'num_of_submissions', 'downloadable',
            'last_submission_time', 'date_created', 'url'
        )


class BaseProjectSerializer(serializers.HyperlinkedModelSerializer):
    projectid = serializers.ReadOnlyField(source='id')
    url = serializers.HyperlinkedIdentityField(
        view_name='project-detail', lookup_field='pk')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail', source='organization',
        lookup_field='username',
        queryset=User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='username',
        read_only=True
    )
    metadata = JsonField(required=False)
    starred = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    forms = serializers.SerializerMethodField()
    public = serializers.BooleanField(source='shared')
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField()
    last_submission_date = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()

    class Meta:
        model = Project
        exclude = ('shared', 'organization', 'user_stars')

    def get_starred(self, obj):
        request = self.context['request']
        user = request.user
        user_stars = obj.user_stars.all()
        if user in user_stars:
            return True

        return False

    def get_users(self, obj):
        if obj:
            users = cache.get('{}{}'.format(BASE_PROJ_USERS_CACHE, obj.pk))
            if users:
                return users

            request = self.context['request']
            user = request.user
            data = {}

            for perm in obj.projectuserobjectpermission_set.filter(user=user):
                if perm.user_id not in data:
                    user = perm.user
                    data[perm.user_id] = {}
                    data[perm.user_id]['permissions'] = []
                    data[perm.user_id]['is_org'] = is_organization(
                        user.profile
                    )
                    data[perm.user_id]['gravatar'] = user.profile.gravatar
                    data[perm.user_id]['first_name'] = user.first_name
                    data[perm.user_id]['last_name'] = user.last_name
                    data[perm.user_id]['user'] = user.username
                data[perm.user_id]['permissions'].append(
                    perm.permission.codename
                )

            results = []
            for k, v in data.items():
                v['role'] = get_role(v['permissions'], obj)

                del(v['permissions'])
                results.append(v)

            cache.set('{}{}'.format(BASE_PROJ_USERS_CACHE, obj.pk), results)

            return results

        return []

    @profile("get_project_forms.prof")
    @check_obj
    def get_forms(self, obj):
        if obj:
            forms = cache.get('{}{}'.format(BASE_PROJ_FORMS_CACHE, obj.pk))
            if forms:
                return forms

            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.filter(
                    deleted_at__isnull=True)
            request = self.context.get('request')
            serializer = BaseProjectXFormSerializer(
                xforms, context={'request': request}, many=True
            )
            forms = list(serializer.data)
            cache.set('{}{}'.format(BASE_PROJ_FORMS_CACHE, obj.pk), forms)

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

            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.all()
            count = len(xforms)
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
            last_submission_date = cache.get('{}{}'.format(
                PROJ_SUB_DATE_CACHE, obj.pk))
            if last_submission_date:
                return last_submission_date
            dates = []
            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.all()
            for x in xforms:
                if x.last_submission_time is not None:
                    dates.append(x.last_submission_time)
            dates.sort()
            dates.reverse()
            last_submission_date = dates[0] if len(dates) else None

            cache.set('{}{}'.format(PROJ_SUB_DATE_CACHE, obj.pk),
                      last_submission_date)

            return last_submission_date

        return None

    def get_teams(self, obj):
        def get_team_permissions(team, obj):
            return [
                p.permission.codename
                for p in obj.projectgroupobjectpermission_set.all()
                if p.group.pk == team.pk
            ]

        if obj:
            teams_users = cache.get('{}{}'.format(
                PROJ_TEAM_USERS_CACHE, obj.pk))
            if teams_users:
                return teams_users

            teams_users = []
            teams = obj.organization.team_set.all()

            for team in teams:
                users = []
                for user in team.user_set.all():
                    users.append(user.username)
                perms = get_team_permissions(team, obj)

                teams_users.append({
                    "name": team.name,
                    "role": get_role(perms, obj),
                    "users": users
                })

            cache.set('{}{}'.format(PROJ_TEAM_USERS_CACHE, obj.pk),
                      teams_users)
            return teams_users

        return []


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    projectid = serializers.ReadOnlyField(source='id')
    url = serializers.HyperlinkedIdentityField(
        view_name='project-detail', lookup_field='pk')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail', source='organization',
        lookup_field='username',
        queryset=User.objects.exclude(pk=settings.ANONYMOUS_USER_ID)
    )
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='username',
        read_only=True
    )
    metadata = JsonField(required=False)
    starred = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    forms = serializers.SerializerMethodField()
    public = serializers.BooleanField(source='shared')
    tags = TagListSerializer(read_only=True)
    num_datasets = serializers.SerializerMethodField()
    last_submission_date = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    data_views = serializers.SerializerMethodField()

    class Meta:
        model = Project
        exclude = ('shared', 'organization', 'user_stars')

    def validate(self, attrs):
        name = attrs.get('name')
        organization = attrs.get('organization')
        if not self.instance and \
                Project.objects.filter(name__iexact=name,
                                       organization=organization):
            raise serializers.ValidationError({
                'name': _(u"Project {} already exists.".format(name))
            })

        return attrs

    def update(self, instance, validated_data):
        metadata = JsonField.to_json(validated_data.get('metadata'))
        owner = validated_data.get('organization')

        if self.partial and metadata:
            if not isinstance(instance.metadata, dict):
                instance.metadata = {}

            instance.metadata.update(metadata)
            validated_data['metadata'] = instance.metadata

        if self.partial and owner:
            # give the new owner permissions
            set_owners_permission(owner, instance)

            if is_organization(owner.profile):
                owners_team = get_organization_owners_team(owner.profile)
                members_team = get_organization_members_team(owner.profile)
                OwnerRole.add(owners_team, instance)
                ReadOnlyRole.add(members_team, instance)

            # clear cache
            safe_delete('{}{}'.format(PROJ_PERM_CACHE, instance.pk))

        project = super(ProjectSerializer, self)\
            .update(instance, validated_data)

        project.xform_set.exclude(shared=project.shared)\
            .update(shared=project.shared, shared_data=project.shared)

        return instance

    def create(self, validated_data):
        created_by = self.context['request'].user
        project = Project.objects.create(
            name=validated_data.get('name'),
            organization=validated_data.get('organization'),
            created_by=created_by,
            shared=validated_data.get('shared', False),
            metadata=validated_data.get('metadata')
        )

        project.xform_set.exclude(shared=project.shared)\
            .update(shared=project.shared, shared_data=project.shared)

        return project

    def get_users(self, obj):
        if obj:
            users = cache.get('{}{}'.format(PROJ_PERM_CACHE, obj.pk))
            if users:
                return users
            data = {}
            for perm in obj.projectuserobjectpermission_set.all():
                if perm.user_id not in data:
                    user = perm.user
                    data[perm.user_id] = {}
                    data[perm.user_id]['permissions'] = []
                    data[perm.user_id]['is_org'] = is_organization(
                        user.profile
                    )
                    data[perm.user_id]['gravatar'] = user.profile.gravatar
                    data[perm.user_id]['metadata'] = user.profile.metadata
                    data[perm.user_id]['first_name'] = user.first_name
                    data[perm.user_id]['last_name'] = user.last_name
                    data[perm.user_id]['user'] = user.username
                data[perm.user_id]['permissions'].append(
                    perm.permission.codename
                )

            results = []
            for k, v in data.items():
                v['permissions'].sort()
                v['role'] = get_role(v['permissions'], obj)
                results.append(v)

            cache.set('{}{}'.format(PROJ_PERM_CACHE, obj.pk), results)

            return results

        return []

    @profile("get_project_forms.prof")
    @check_obj
    def get_forms(self, obj):
        if obj:
            forms = cache.get('{}{}'.format(PROJ_FORMS_CACHE, obj.pk))
            if forms:
                return forms
            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.filter(
                    deleted_at__isnull=True)
            request = self.context.get('request')
            serializer = ProjectXFormSerializer(
                xforms, context={'request': request}, many=True
            )
            forms = list(serializer.data)
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

            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.all()
            count = len(xforms)
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
            last_submission_date = cache.get('{}{}'.format(
                PROJ_SUB_DATE_CACHE, obj.pk))
            if last_submission_date:
                return last_submission_date
            dates = []
            xforms = obj.xforms_prefetch \
                if hasattr(obj, 'xforms_prefetch') else obj.xform_set.all()
            for x in xforms:
                if x.last_submission_time is not None:
                    dates.append(x.last_submission_time)
            dates.sort()
            dates.reverse()
            last_submission_date = dates[0] if len(dates) else None

            cache.set('{}{}'.format(PROJ_SUB_DATE_CACHE, obj.pk),
                      last_submission_date)

            return last_submission_date

        return None

    def get_starred(self, obj):
        request = self.context['request']
        user = request.user
        user_stars = obj.user_stars.all()
        if user in user_stars:
            return True

        return False

    def get_teams(self, obj):
        def get_team_permissions(team, obj):
            return [
                p.permission.codename
                for p in obj.projectgroupobjectpermission_set.all()
                if p.group.pk == team.pk
            ]

        if obj:
            teams_users = cache.get('{}{}'.format(
                PROJ_TEAM_USERS_CACHE, obj.pk))
            if teams_users:
                return teams_users

            teams_users = []
            teams = obj.organization.team_set.all()

            for team in teams:
                users = []
                for user in team.user_set.all():
                    users.append(user.username)
                perms = get_team_permissions(team, obj)

                teams_users.append({
                    "name": team.name,
                    "role": get_role(perms, obj),
                    "users": users
                })

            cache.set('{}{}'.format(PROJ_TEAM_USERS_CACHE, obj.pk),
                      teams_users)
            return teams_users

        return []

    def get_data_views(self, obj):
        if obj:
            data_views = cache.get(
                '{}{}'.format(PROJECT_LINKED_DATAVIEWS, obj.pk))
            if data_views:
                return data_views

            data_views_obj = obj.dataview_prefetch if \
                hasattr(obj, 'dataview_prefetch') else obj.dataview_set.all()

            serializer = DataViewSerializer(
                data_views_obj,
                many=True,
                context=self.context)
            data_views = list(serializer.data)

            cache.set(
                '{}{}'.format(PROJECT_LINKED_DATAVIEWS, obj.pk), data_views)

            return data_views
        return []
