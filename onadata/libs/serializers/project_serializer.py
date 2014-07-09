from rest_framework import serializers

from onadata.apps.api.models import Project
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.json_field import JsonField


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    projectid = serializers.Field(source='id')
    url = serializers.HyperlinkedIdentityField(
        view_name='project-detail', lookup_field='pk')
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='organization', lookup_field='username')
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    metadata = JsonField()
    users = serializers.SerializerMethodField('get_project_permissions')

    class Meta:
        model = Project
        exclude = ('organization', 'created_by')

    def restore_object(self, attrs, instance=None):
        if instance:
            metadata = JsonField.to_json(attrs.get('metadata'))
            if self.partial:
                instance.metadata.update(metadata)
                attrs['metadata'] = instance.metadata
            return super(ProjectSerializer, self)\
                .restore_object(attrs, instance)
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
