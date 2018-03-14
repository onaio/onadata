# -*- coding: utf-8 -*-
"""
Messaging notification backend for MQTT
"""
from __future__ import unicode_literals

import json

import paho.mqtt.client as paho

from onadata.apps.messaging.backends.base import BaseBackend


class MQTTBackend(BaseBackend):
    """
    Notification backend for MQTT
    """

    def __init__(self, options=None):
        super(MQTTBackend, self).__init__()
        if not options:
            raise Exception("MQTT Backend expects configuration options.")

        host = options.get('HOST')
        if not host:
            raise Exception("An MQTT host is required.")
        self.qos = options.get('QOS', 0)
        self.retain = options.get('RETAIN', False)
        self.topic_base = options.get('TOPIC_BASE', 'onadata')

        self.client = paho.Client()
        self.client.connect(host)

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
            'topic_base': self.topic_base
        }
        return (
            '/{topic_base}/{target_name}/{target_id}/messages/publish'.format(
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
