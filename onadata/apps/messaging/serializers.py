# -*- coding: utf-8 -*-
"""
Message serializers
"""

from __future__ import unicode_literals
from typing import Union

import json

from actstream.actions import action_handler
from actstream.models import Action
from actstream.signals import action
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.translation import ugettext as _
from rest_framework import exceptions, serializers

from onadata.apps.messaging.constants import MESSAGE, MESSAGE_VERBS
from onadata.apps.messaging.utils import TargetDoesNotExist, get_target


class ContentTypeChoiceField(serializers.ChoiceField):
    """
    Custom ChoiceField that gets the model name from a ContentType object
    """

    # pylint: disable=no-self-use
    def to_representation(self, value):
        """
        Get the model from ContentType object
        """
        return value.model


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer class for Message objects
    """
    TARGET_CHOICES = (('xform', 'XForm'), ('project', 'Project'),
                      ('user', 'User'))  # yapf: disable

    message = serializers.CharField(source='description', allow_blank=False)
    target_id = serializers.IntegerField(source='target_object_id')
    target_type = ContentTypeChoiceField(
        TARGET_CHOICES, source='target_content_type')
    user = serializers.CharField(source='actor', required=False)
    verb = serializers.ChoiceField(MESSAGE_VERBS, default=MESSAGE)

    class Meta:
        """
        MessageSerializer metadata
        """
        model = Action
        fields = ['id', 'verb', 'message', 'user', 'target_id', 'target_type',
                  'timestamp']

    def __init__(self, *args, **kwargs):
        super(MessageSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        full_message_payload = getattr(settings, 'FULL_MESSAGE_PAYLOAD', False)
        if request and request.method == 'GET' and not full_message_payload:
            extra_fields = ['target_type', 'target_id']
            for field in extra_fields:
                self.fields.pop(field)

    def create(self, validated_data):
        """
        Creates the Message in the Action model
        """
        request = self.context['request']
        target_type = validated_data.get("target_content_type")
        target_id = validated_data.get("target_object_id")
        verb = validated_data.get("verb", MESSAGE)
        try:
            content_type = get_target(target_type)
        except TargetDoesNotExist:
            raise serializers.ValidationError({
                'target_type': _('Unknown target type')
            })  # yapf: disable
        else:
            try:
                target_object = \
                    content_type.get_object_for_this_type(pk=target_id)
            except content_type.model_class().DoesNotExist:
                raise serializers.ValidationError({
                    'target_id': _('target_id not found')
                })  # yapf: disable
            else:
                # check if request.user has permission to the target_object
                permission = '{}.change_{}'.format(
                    target_object._meta.app_label,
                    target_object._meta.model_name)
                if not request.user.has_perm(permission, target_object) \
                        and verb == MESSAGE:
                    message = (_("You do not have permission to add messages "
                               "to target_id %s.") % target_object)
                    raise exceptions.PermissionDenied(detail=message)
                results = action.send(
                    request.user,
                    verb=verb,
                    target=target_object,
                    description=validated_data.get("description"))

                # results will be a list of tuples with the first item in the
                # tuple being the signal handler function and the second
                # being the object.  We want to get the object of the first
                # element in the list whose function is `action_handler`

                try:
                    instance = [
                        instance for (receiver, instance) in results
                        if receiver == action_handler
                    ].pop()
                except IndexError:
                    # if you get here it means we have no instances
                    raise serializers.ValidationError(
                        "Message not created. Please retry.")
                else:
                    return instance


def send_message(
        instance_id: Union[list, int],
        target_id: int,
        target_type: str, user: User, message_verb: str):
    """
    Send a message.
    :param id: A single ID or list of IDs that have been affected by an action
    :param target_id: id of the target_type
    :param target_type: any of these three ['xform', 'project', 'user']
    :param request: http request object
    :return:
    """
    message_id_limit = getattr(settings, 'NOTIFICATION_ID_LIMIT', 100)
    if user:
        if isinstance(instance_id, int):
            instance_id = [instance_id]
        request = HttpRequest()
        request.user = user

        data = {
            "target_id": target_id,
            "target_type": target_type,
            "verb": message_verb
        }

        # If ID is a list and the message limit on the amount of IDs
        # in one message is passed. Split the ids into
        # chunks
        if isinstance(instance_id, list) and\
                len(instance_id) > message_id_limit:
            ids = instance_id
            while len(ids) > 0:
                data["message"] = json.dumps({'id': ids[:message_id_limit]})
                message = MessageSerializer(
                    data=data, context={"request": request})
                del ids[:message_id_limit]
                if message.is_valid():
                    message.save()
        else:
            data["message"] = json.dumps({'id': instance_id})
            message = MessageSerializer(
                data=data, context={"request": request})
            if message.is_valid():
                message.save()
