from django.forms import widgets
from rest_framework import serializers
from django.core.cache import cache

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import Project
from onadata.libs.permissions import get_object_users_with_permissions,\
    OwnerRole
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.libs.utils.decorators import check_obj


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
        project_serializer = cache.get('ProjectSerializer:get_project_permissions')
        if project_serializer:
            users = project_serializer.get(obj.pk)
            if users:
                return users
            else:
                user = get_object_users_with_permissions(obj)
                project_serializer.update({obj.pk: users})
                return user
        user = get_object_users_with_permissions(obj)
        cache.set('ProjectSerializer:get_project_permissions', {obj.pk: user})
        return user

    @check_obj
    def get_project_forms(self, obj):
        project_serializer = cache.get('ProjectSerializer:get_project_forms')
        if project_serializer:
            forms = project_serializer.get(obj.pk)
            if forms:
                return forms
            else:
                xforms_details = obj.xform_set.values('pk', 'title')
                forms = [{'name': form['title'], 'id':form['pk']}
                         for form in xforms_details]
                project_serializer.update({obj.pk: forms})
                return forms

        xforms_details = obj.xform_set.values('pk', 'title')

        forms = [{'name': form['title'], 'id':form['pk']}
                for form in xforms_details]
        cache.set('ProjectSerializer:get_project_forms', {obj.pk: forms})
        return forms

    @check_obj
    def get_num_datasets(self, obj):
        """Return the number of datasets attached to the object.

        :param obj: The project to find datasets for.
        """
        project_serializer = cache.get('ProjectSerializer:get_num_datasets')
        if project_serializer:
            count = project_serializer.get(obj.pk)
            if count:
                return count
            else:
                count = obj.xform_set.count()
                project_serializer.update({obj.pk: count})
                return count

        count = obj.xform_set.count()
        cache.set('ProjectSerializer:get_num_datasets', {obj.pk: count})
        return count

    @check_obj
    def get_last_submission_date(self, obj):
        """Return the most recent submission date to any of the projects
        datasets.

        :param obj: The project to find the last submission date for.
        """
        project_serializer = cache.get('ProjectSerializer:get_last_submission_date')
        if project_serializer:
            last_submission = project_serializer.get(obj.pk)
            if last_submission:
                return last_submission
            else:
                xform_ids = obj.xform_set.values_list('pk', flat=True)
                last_submission = Instance.objects.\
                    order_by('-date_created').\
                    filter(xform_id__in=xform_ids).values_list('date_created',
                                                       flat=True)

                project_serializer.update({obj.pk: last_submission and last_submission[0]})
                return last_submission and last_submission[0]

        xform_ids = obj.xform_set.values_list('pk', flat=True)
        last_submission = Instance.objects.\
            order_by('-date_created').\
            filter(xform_id__in=xform_ids).values_list('date_created',
                                                       flat=True)
        cache.set("ProjectSerializer:get_last_submission_date",
                  {obj.pk: last_submission and last_submission[0]})
        return last_submission and last_submission[0]

    def is_starred_project(self, obj):
        request = self.context['request']
        user = request.user
        user_stars = obj.user_stars.all()
        if user in user_stars:
            return True

        return False
