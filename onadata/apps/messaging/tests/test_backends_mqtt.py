# -*- coding: utf-8 -*-
"""
Tests for MQTT notification backend
"""
from __future__ import unicode_literals

import json

from django.test import TestCase

from onadata.apps.messaging.backends.mqtt import MQTTBackend
from onadata.apps.messaging.tests.test_base import (_create_message,
                                                    _create_user)


class TestMQTTBackend(TestCase):
    """
    Test MQTT Backend
    """

    def test_mqtt_get_topic(self):
        """
        Test MQTT backend get_topic method
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')
        mqtt = MQTTBackend(host='localhost')
        expected = (
            "/{topic_root}/{target_name}/{target_id}/messages/publish".format(
                topic_root='onadata', target_name='user',
                target_id=to_user.id))
        self.assertEqual(expected, mqtt.get_topic(instance))

    def test_mqtt_get_payload(self):
        """
        Test MQTT backend get_payload method
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')
        mqtt = MQTTBackend(host='localhost')
        payload = {
            'id': instance.id,
            'time': instance.timestamp.isoformat(),
            'payload': {
                'author': {
                    'username': from_user.username,
                    'real_name': from_user.get_full_name()
                },
                'context': {
                    'type': to_user._meta.model_name,
                },
                'message': "I love oov"
            }
        }
        self.assertEqual(json.dumps(payload), mqtt.get_payload(instance))

    def test_mqqt_send(self):
        """
        Test MQTT Backend send method
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')
        mqtt = MQTTBackend(host='localhost')
        result = mqtt.send(instance=instance)
        self.assertTrue(result.is_published())
