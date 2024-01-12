from rest_framework import serializers

from onadata.apps.logger.models import EntityList, Project


class EntityListSerializer(serializers.HyperlinkedModelSerializer):
    """Default Serializer for EntityLists"""

    url = serializers.HyperlinkedIdentityField(
        view_name="entity_list-detail", lookup_field="pk"
    )
    project = serializers.HyperlinkedRelatedField(
        view_name="project-detail",
        lookup_field="pk",
        queryset=Project.objects.all(),
    )
    num_registration_forms = serializers.SerializerMethodField()
    num_follow_up_forms = serializers.SerializerMethodField()

    def get_num_registration_forms(self, obj) -> int:
        """Returns number of RegistrationForms for EntityList object"""
        return obj.registration_forms.count()

    def get_num_follow_up_forms(self, obj) -> int:
        """Returns number of FollowUpForms consuming Entities from dataset"""
        return obj.follow_up_forms.count()

    class Meta:
        model = EntityList
        fields = (
            "url",
            "id",
            "name",
            "project",
            "num_registration_forms",
            "num_follow_up_forms",
        )
