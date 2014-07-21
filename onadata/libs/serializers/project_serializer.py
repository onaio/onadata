from django.forms import widgets
from rest_framework import serializers

from onadata.apps.api.models import Project
from onadata.libs.permissions import get_object_users_with_permissions
from onadata.libs.serializers.fields.boolean_field import BooleanField
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.libs.serializers.tag_list_serializer import TagListSerializer


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
    users = serializers.SerializerMethodField('get_project_permissions')
    public = BooleanField(
        source='shared', widget=widgets.CheckboxInput())
    tags = TagListSerializer(read_only=True)

    class Meta:
        model = Project
        exclude = ('organization', 'created_by', 'user_stars')

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
