# -*- coding: utf-8 -*-
"""
Message serializers
"""

import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from actstream.actions import action_handler
from actstream.models import Action
from actstream.signals import action
from rest_framework import exceptions, serializers

from onadata.apps.messaging.constants import MESSAGE, MESSAGE_VERBS
from onadata.apps.messaging.utils import TargetDoesNotExist, get_target
from onadata.libs.utils.common_tools import report_exception

User = get_user_model()


class ContentTypeChoiceField(serializers.ChoiceField):
    """
    Custom ChoiceField that gets the model name from a ContentType object
    """

    def to_representation(self, value):
        """
        Get the model from ContentType object
        """
        return value.model


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer class for Message objects
    """

    TARGET_CHOICES = (
        ("xform", "XForm"),
        ("project", "Project"),
        ("user", "User"),
    )  # yapf: disable

    message = serializers.CharField(source="description", allow_blank=False)
    target_id = serializers.IntegerField(source="target_object_id")
    target_type = ContentTypeChoiceField(TARGET_CHOICES, source="target_content_type")
    user = serializers.CharField(source="actor", required=False)
    verb = serializers.ChoiceField(MESSAGE_VERBS, default=MESSAGE)

    class Meta:
        """
        MessageSerializer metadata
        """

        model = Action
        fields = [
            "id",
            "verb",
            "message",
            "user",
            "target_id",
            "target_type",
            "timestamp",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        full_message_payload = getattr(settings, "FULL_MESSAGE_PAYLOAD", False)
        if request and request.method == "GET" and not full_message_payload:
            extra_fields = ["target_type", "target_id"]
            for field in extra_fields:
                self.fields.pop(field)

    def create(self, validated_data):
        """
        Creates the Message in the Action model
        """
        request = self.context["request"]
        target_type = validated_data.get("target_content_type")
        target_id = validated_data.get("target_object_id")
        verb = validated_data.get("verb", MESSAGE)
        try:
            content_type = get_target(target_type)
        except TargetDoesNotExist as exc:
            raise serializers.ValidationError(
                {"target_type": _("Unknown target type")}
            ) from exc  # yapf: disable
        try:
            target_object = content_type.get_object_for_this_type(pk=target_id)
        except content_type.model_class().DoesNotExist as exc:
            raise serializers.ValidationError(
                {"target_id": _("target_id not found")}
            ) from exc  # yapf: disable
        # check if request.user has permission to the target_object
        permission = (
            f"{target_object._meta.app_label}.change_{target_object._meta.model_name}"
        )
        if not request.user.has_perm(permission, target_object) and verb == MESSAGE:
            message = (
                _("You do not have permission to add messages to target_id %s.")
                % target_object
            )
            raise exceptions.PermissionDenied(detail=message)
        results = action.send(
            request.user,
            verb=verb,
            target=target_object,
            description=validated_data.get("description"),
        )

        # results will be a list of tuples with the first item in the
        # tuple being the signal handler function and the second
        # being the object.  We want to get the object of the first
        # element in the list whose function is `action_handler`

        try:
            # pylint: disable=comparison-with-callable
            instance = [
                instance
                for (receiver, instance) in results
                if receiver.__module__ == action_handler.__module__
                and receiver.__name__ == action_handler.__name__
            ]
            instance = instance[0]
        except IndexError as exc:
            report_exception("(debug) index error", exc, sys.exc_info())
            # if you get here it means we have no instances
            raise serializers.ValidationError(
                "Message not created. Please retry."
            ) from exc
        return instance
