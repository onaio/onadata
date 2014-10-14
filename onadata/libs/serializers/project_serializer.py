from django.forms import widgets
from rest_framework import serializers

from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.project import Project


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

            if self.partial and metadata:
                if not isinstance(instance.metadata, dict):
                    instance.metadata = {}

                instance.metadata.update(metadata)
                attrs['metadata'] = instance.metadata

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

    def get_project_permissions(self, obj):
        return get_object_users_with_permissions(obj)

    def get_project_forms(self, obj):
        if obj is not None:
            xforms_details = obj.projectxform_set.values(
                'xform__pk', 'xform__title')
            return [{'name': form['xform__title'], 'id':form['xform__pk']}
                    for form in xforms_details]

    def get_num_datasets(self, obj):
        """Return the number of datasets attached to the object.

        :param obj: The project to find datasets for.
        """
        if obj:
            return obj.projectxform_set.count()

    def get_last_submission_date(self, obj):
        """Return the most recent submission date to any of the projects
        datasets.

        :param obj: The project to find the last submission date for.
        """
        if obj:
            xform_ids = obj.projectxform_set.values_list('xform', flat=True)
            last_submission = Instance.objects.\
                order_by('-date_created').\
                filter(xform_id__in=xform_ids).values_list('date_created',
                                                           flat=True)

            return last_submission and last_submission[0]

    def is_starred_project(self, obj):
        request = self.context['request']
        user = request.user
        user_stars = obj.user_stars.all()
        if user in user_stars:
            return True

        return False
