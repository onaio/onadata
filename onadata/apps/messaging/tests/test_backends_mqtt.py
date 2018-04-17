# -*- coding: utf-8 -*-
"""
Tests for MQTT notification backend
"""
from __future__ import unicode_literals

import json
import ssl

from django.test import TestCase

from mock import MagicMock, patch

from onadata.apps.messaging.backends.mqtt import (MQTTBackend, get_payload,
                                                  get_target_metadata)
from onadata.apps.messaging.constants import PROJECT, XFORM
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
        mqtt = MQTTBackend(options={'HOST': 'localhost'})
        expected = (
            "/{topic_root}/{target_name}/{target_id}/messages/publish".format(
                topic_root='onadata', target_name='user',
                target_id=to_user.id))
        self.assertEqual(expected, mqtt.get_topic(instance))

    def test_get_target_metadata(self):
        """
        Test MQTT backend get_target_metadata function
        """

        # User objects
        user = _create_user('John')
        user_metadata = {'id': user.pk, 'name': user.get_full_name()}
        self.assertEqual(
            json.dumps(user_metadata), json.dumps(get_target_metadata(user)))

        # XForm objects
        xform = MagicMock()
        xform.pk = 1337
        xform.title = 'Test Form'
        xform.id_string = 'Test_Form_ID'
        xform._meta.model_name = XFORM
        xform_metadata = {
            'id': 1337,
            'name': 'Test Form',
            'form_id': 'Test_Form_ID'
        }
        self.assertEqual(
            json.dumps(xform_metadata), json.dumps(get_target_metadata(xform)))

        # Project objects
        project = MagicMock()
        project.pk = 7331
        project.name = 'Test Project'
        project._meta.model_name = PROJECT
        project_metadata = {'id': 7331, 'name': 'Test Project'}
        self.assertEqual(
            json.dumps(project_metadata),
            json.dumps(get_target_metadata(project)))

    def test_mqtt_get_payload(self):
        """
        Test MQTT backend get_payload function
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')

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
                    'metadata': {
                        'id': to_user.pk,
                        'name': to_user.get_full_name()
                    }
                },
                'message': "I love oov"
            }
        }
        self.assertEqual(json.dumps(payload), get_payload(instance))

    @patch('onadata.apps.messaging.backends.mqtt.publish.single')
    def test_mqtt_send(self, mocked):
        """
        Test MQTT Backend send method
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')
        mqtt = MQTTBackend(options={
            'HOST': 'localhost',
            'PORT': 8883,
            'SECURE': True,
            'CA_CERT_FILE': 'cacert.pem',
            'CERT_FILE': 'emq.pem',
            'KEY_FILE': 'emq.key'
        })
        mqtt.send(instance=instance)
        self.assertTrue(mocked.called)
        args, kwargs = mocked.call_args_list[0]
        self.assertEquals(mqtt.get_topic(instance), args[0])
        self.assertEquals(get_payload(instance), kwargs['payload'])
        self.assertEquals('localhost', kwargs['hostname'])
        self.assertEquals(8883, kwargs['port'])
        self.assertEquals(0, kwargs['qos'])
        self.assertEquals(False, kwargs['retain'])
        self.assertDictEqual(
            dict(ca_certs='cacert.pem',
                 certfile='emq.pem',
                 keyfile='emq.key',
                 tls_version=ssl.PROTOCOL_TLSv1_2,
                 cert_reqs=ssl.CERT_NONE),
            kwargs['tls'])
