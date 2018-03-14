# -*- coding: utf-8 -*-
"""
Messaging notification backend for MQTT
"""
from __future__ import unicode_literals

import json

import paho.mqtt.client as paho
from django.conf import settings

from onadata.apps.messaging.backends.base import BaseBackend


class MQTTBackend(BaseBackend):
    """
    Notification backend for MQTT
    """
    host = getattr(settings, 'MESSAGING_MQTT_IP_ADDRESS', None)

    def __init__(self, host=None, qos=0, retain=False):
        if not self.host and not host:
            raise Exception("An MQTT host is required.")

        self.client = paho.Client()
        self.client.connect(host or self.host)
        self.qos = qos
        self.retain = retain
        self.topic_root = 'onadata'

    def get_topic(self, instance):
        """
        Constructs the message topic

        For sending messages it should look like:
            /onadata/forms/[pk or uuid]/messages/publish
            /onadata/projects/[pk or uuid]/messages/publish
            /onadata/users/[pk or uuid]/messages/publish
        """
        kwargs = {
            'target_id': instance.target_object_id,
            'target_name': instance.target._meta.model_name,
            'topic_root': self.topic_root
        }
        return (
            '/{topic_root}/{target_name}/{target_id}/messages/publish'.format(
                **kwargs))

    def get_payload(self, instance):  # pylint: disable=no-self-use
        """
        Constructs the message payload
        """
        payload = {
            'id': instance.id,
            'time': instance.timestamp.isoformat(),
            'payload': {
                'author': {
                    'username': instance.actor.username,
                    'real_name': instance.actor.get_full_name()
                },
                'context': {
                    'type': instance.target._meta.model_name,
                },
                'message': instance.description
            }
        }

        return json.dumps(payload)

    def send(self, instance):
        """
        Sends the message to appropriate MQTT topic(s)
        """
        topic = self.get_topic(instance)
        payload = self.get_payload(instance)
        result = self.client.publish(
            topic, payload=payload, qos=self.qos, retain=self.retain)
        self.client.disconnect()

        return result
