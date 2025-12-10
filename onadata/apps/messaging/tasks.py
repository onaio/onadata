# -*- coding: utf-8 -*-
"""
Messaging tasks
"""

from __future__ import unicode_literals

import json
from typing import Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, OperationalError
from django.http import HttpRequest

from multidb.pinning import use_master

from onadata.apps.messaging.backends.base import call_backend
from onadata.apps.messaging.serializers import MessageSerializer
from onadata.celeryapp import app

User = get_user_model()


@app.task(ignore_result=True)
def call_backend_async(backend, instance_id, backend_options=None):
    """
    Task to send messages to notification backeds such as MQTT
    """
    call_backend(backend, instance_id, backend_options)


# pylint: disable=too-few-public-methods
class AutoRetryTask(app.Task):
    """Base task class for retrying exceptions"""

    retry_backoff = 3
    autoretry_for = (DatabaseError, ConnectionError, OperationalError)
    max_retries = 5


# pylint: disable=too-many-arguments,too-many-positional-arguments
@app.task(base=AutoRetryTask)
@use_master
def send_message(
    instance_id: Union[list, int],
    target_id: int,
    target_type: str,
    user: int,
    message_verb: str,
    message_description: Optional[str] = None,
):
    """
    Send a message.
    :param id: A single ID or list of IDs that have been affected by an action
    :param target_id: id of the target_type
    :param target_type: any of these three ['xform', 'project', 'user']
    :param user: User object or user ID
    :param request: http request object
    :return:
    """
    message_id_limit = getattr(settings, "NOTIFICATION_ID_LIMIT", 100)

    if user:
        if isinstance(instance_id, int):
            instance_id = [instance_id]
        request = HttpRequest()
        request.user = User.objects.get(pk=user)
        data = {
            "target_id": target_id,
            "target_type": target_type,
            "verb": message_verb,
        }

        # Split the ids into chunks
        if isinstance(instance_id, list):
            ids = instance_id
            while len(ids) > 0:
                data["message"] = json.dumps(
                    {
                        "id": ids[:message_id_limit],
                    }
                    | _create_description_map(message_description)
                )
                message = MessageSerializer(data=data, context={"request": request})
                del ids[:message_id_limit]
                if message.is_valid():
                    message.save()


def _create_description_map(message_description):
    """
    Create a description map if message is provided
    """
    return {"description": message_description} if message_description else {}
