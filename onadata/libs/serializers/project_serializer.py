from rest_framework import serializers

from onadata.libs.serializers.fields.hyperlinked_multi_identity_field import\
    HyperlinkedMultiIdentityField
from onadata.apps.api.models import Project


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    url = HyperlinkedMultiIdentityField(
        view_name='project-detail',
        lookup_fields=(('pk', 'pk'), ('owner', 'organization')))
    owner = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        source='organization', lookup_field='username')
    created_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)

    class Meta:
        model = Project
        exclude = ('organization', 'created_by')

    def restore_object(self, attrs, instance=None):
        if instance:
            return super(ProjectSerializer, self)\
                .restore_object(attrs, instance)
        if 'request' in self.context:
            created_by = self.context['request'].user
            return Project(
                name=attrs.get('name'),
                organization=attrs.get('organization'),
                created_by=created_by,)
        return attrs
