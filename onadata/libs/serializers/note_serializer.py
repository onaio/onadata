from django.utils.translation import ugettext as _
from guardian.shortcuts import assign_perm
from rest_framework import exceptions
from rest_framework import serializers

from onadata.apps.logger.models import Note


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note

    def create(self, validated_data):
        obj = super(NoteSerializer, self).create(validated_data)
        request = self.context.get('request')

        if request:
            assign_perm('add_note', request.user, obj)
            assign_perm('change_note', request.user, obj)
            assign_perm('delete_note', request.user, obj)
            assign_perm('view_note', request.user, obj)

        # should update instance json
        obj.instance.parsed_instance.save()

        return obj

    def validate(self, attrs):
        instance = attrs.get('instance')
        request = self.context.get('request')
        if request and \
                not request.user.has_perm('change_xform', instance.xform):
            raise exceptions.PermissionDenied(_(
                u"You are not authorized to add/change notes on this form."
            ))

        return attrs
