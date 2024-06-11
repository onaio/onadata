from django.utils.translation import gettext as _

from rest_framework import serializers

from onadata.apps.logger.models import (
    Entity,
    EntityList,
    FollowUpForm,
    Project,
    RegistrationForm,
    XForm,
)


class EntityListSerializer(serializers.HyperlinkedModelSerializer):
    """Default Serializer for EntityList"""

    url = serializers.HyperlinkedIdentityField(
        view_name="entity_list-detail", lookup_field="pk"
    )
    project = serializers.HyperlinkedRelatedField(
        view_name="project-detail",
        lookup_field="pk",
        queryset=Project.objects.all(),
    )
    public = serializers.BooleanField(source="project.shared")
    num_registration_forms = serializers.SerializerMethodField()
    num_follow_up_forms = serializers.SerializerMethodField()

    def get_num_registration_forms(self, obj: EntityList) -> int:
        """Returns number of RegistrationForms for EntityList object"""
        return obj.registration_forms.count()

    def get_num_follow_up_forms(self, obj: EntityList) -> int:
        """Returns number of FollowUpForms consuming Entities from dataset"""
        return obj.follow_up_forms.count()

    class Meta:
        model = EntityList
        fields = (
            "url",
            "id",
            "name",
            "project",
            "public",
            "date_created",
            "date_modified",
            "num_registration_forms",
            "num_follow_up_forms",
            "num_entities",
        )


class RegistrationFormInlineSerializer(serializers.HyperlinkedModelSerializer):
    """Inline serializer for RegistrationForm"""

    title = serializers.CharField(source="xform.title")
    xform = serializers.HyperlinkedRelatedField(
        view_name="xform-detail",
        lookup_field="pk",
        queryset=XForm.objects.all(),
    )
    id_string = serializers.CharField(source="xform.id_string")
    save_to = serializers.SerializerMethodField()

    def get_save_to(self, obj: RegistrationForm) -> list[str]:
        """Returns the save_to fields defined in the XLSForm"""
        return list(obj.get_save_to().keys())

    class Meta:
        model = RegistrationForm
        fields = (
            "title",
            "xform",
            "id_string",
            "save_to",
        )


class FollowUpFormInlineSerializer(serializers.HyperlinkedModelSerializer):
    """Inline serializer for FollowUpForm"""

    title = serializers.CharField(source="xform.title")
    xform = serializers.HyperlinkedRelatedField(
        view_name="xform-detail",
        lookup_field="pk",
        queryset=XForm.objects.all(),
    )
    id_string = serializers.CharField(source="xform.id_string")

    class Meta:
        model = FollowUpForm
        fields = (
            "title",
            "xform",
            "id_string",
        )


class EntityListDetailSerializer(EntityListSerializer):
    """Serializer for EntityList detail"""

    registration_forms = RegistrationFormInlineSerializer(many=True, read_only=True)
    follow_up_forms = FollowUpFormInlineSerializer(many=True, read_only=True)

    class Meta:
        model = EntityList
        fields = (
            "id",
            "name",
            "project",
            "public",
            "date_created",
            "date_modified",
            "num_registration_forms",
            "num_follow_up_forms",
            "num_entities",
            "registration_forms",
            "follow_up_forms",
        )


class EntitySerializer(serializers.ModelSerializer):
    """Serializer for Entity"""

    label = serializers.CharField(write_only=True, required=False)
    data = serializers.JSONField(write_only=True, required=False)

    def validate_data(self, value):
        if value:
            for key in value.keys():
                if key not in self.context["entity_list"].properties:
                    raise serializers.ValidationError(
                        _(f"Invalid dataset property {key}")
                    )

        return value

    def update(self, instance, validated_data):
        data = validated_data.pop("data", {})
        label = validated_data.pop("label", None)

        if label:
            instance.json["meta/entity/label"] = label

        if data:
            updated_data = {**instance.json, **data}

            for key, value in data.items():
                if not value:
                    # Unset property
                    del updated_data[key]

            instance.json = updated_data

        instance.save()
        instance.history.create(
            json=instance.json, created_by=self.context["request"].user
        )

        return instance

    def to_representation(self, instance):
        return instance.json

    class Meta:
        model = Entity
        fields = (
            "json",
            "label",
            "data",
        )
