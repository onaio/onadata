# -*- coding: utf-8 -*-
"""
Message serializers
"""

from __future__ import unicode_literals

from actstream.actions import action_handler
from actstream.models import Action
from actstream.signals import action
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

APP_LABEL_MAPPING = {
    'xform': 'logger',
    'projects': 'logger',
    'user': 'auth',
}


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer class for Message objects
    """
    TARGET_CHOICES = (('xform', 'XForm'),  ('project', 'Project'),
                      ('user', 'User'))  # yapf: disable

    message = serializers.CharField(source='description', allow_blank=False)
    target_id = serializers.IntegerField(source='target_object_id')
    target_type = serializers.ChoiceField(
        TARGET_CHOICES, source='target_content_type')

    class Meta:
        model = Action
        fields = ['id', 'message', 'target_id', 'target_type']

    def create(self, validated_data):
        """
        Creates the Message in the Action model
        """
        target_type = validated_data.get("target_content_type")
        target_id = validated_data.get("target_object_id")
        app_label = APP_LABEL_MAPPING[target_type]
        try:
            content_type = ContentType.objects.get(
                app_label=app_label, model=target_type)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError({
                'target_type':
                'Unknown target type'
            })
        else:
            target_object = content_type.get_object_for_this_type(pk=target_id)

            # self.context.get('request').user
            from django.contrib.auth.models import User
            user = User.objects.get(pk=target_id)

            results = action.send(
                user,
                verb='message',
                target=target_object,
                description=validated_data.get("description"))

            results = [x for x in results if x[0] == action_handler]
            if not results:
                raise serializers.ValidationError(
                    "Message not created. Please retry.")

            return results[0][1]
