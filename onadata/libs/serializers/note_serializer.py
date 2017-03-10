from django.utils.translation import ugettext as _
from guardian.shortcuts import assign_perm
from rest_framework import exceptions, serializers

from onadata.apps.logger.models import Note


class NoteSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Note

    def get_owner(self, obj):
        if obj and obj.created_by_id:
            return obj.created_by.username

        return None

    def create(self, validated_data):
        request = self.context.get('request')
        obj = super(NoteSerializer, self).create(validated_data)

        if request:
            assign_perm('add_note', request.user, obj)
            assign_perm('change_note', request.user, obj)
            assign_perm('delete_note', request.user, obj)
            assign_perm('view_note', request.user, obj)

        # should update instance json
        obj.instance.save()

        return obj

    def validate(self, attrs):
        instance = attrs.get('instance')
        request = self.context.get('request')

        if request and request.user.is_anonymous():
            raise exceptions.ParseError(
                _(u"You are not authorized to add/change notes on this form."))

        attrs['created_by'] = request.user

        field = attrs.get('instance_field')

        if field and instance.xform.get_label(field) is None:
            raise exceptions.ValidationError(
                "instance_field must be a field on the form")

        return attrs
